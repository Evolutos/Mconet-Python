"""Tests for scheduling service access resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    Extensions,
    Headers,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    UriValue,
)
from mconet.core.runtime._service_access_resolution import resolve_service_access
from mconet.core.runtime.default_service_access_resolver import (
    DefaultServiceAccessResolver,
)
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelTargetMatch,
    ServiceAccessResolver,
    TaskMatch,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep one fixture from mutating another fixture's fields.
    return {}


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural model target carried by the request fixture."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Structural task descriptor. Access resolution does not read it."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Document:
    """Placeholder task document. Access resolution does not read it."""

    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class _Task:
    """Structural task that makes the request a ModelRequest."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request exposing one optional access layer."""

    target: ModelTarget
    task: ModelTaskRequest
    service_access: ServiceAccess | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization decision with no credential payload."""

    kind: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Access:
    """Structural unresolved access value for one source layer."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Component:
    """Runtime component stored as a plan adapter."""

    descriptor: ComponentDescriptor


class _CountingResolver:
    """Count resolve calls and delegate to the default field merger."""

    def __init__(self) -> None:
        """Start from the builtin resolver with a zero call count."""
        self._resolver = DefaultServiceAccessResolver()
        # The scheduler must call resolve once and must not retry a failure.
        self.calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the delegated resolver's diagnostic metadata."""
        return self._resolver.descriptor

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Count one call and return the default resolver's result."""
        self.calls += 1
        return self._resolver.resolve(
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )


def _request(access: ServiceAccess | None = None) -> _Request:
    """Return a request whose only meaningful field is service access."""
    return _Request(
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("protocol.vendor"),
            NamedModel("vendor-model"),
        ),
        _Task(
            _Descriptor(OpenIdentifier("conversation.generate")),
            cast(TaskDocument, _Document()),
        ),
        access,
    )


def _direct_plan() -> ModelIntegrationPlan:
    """Return a direct plan, which has no protocol access default."""
    return ModelIntegrationPlan(
        source="direct_adapter",
        binding_id=None,
        binding_version=None,
        match=None,
        task_protocol_adapter=_Component(
            ComponentDescriptor("adapter", "1.0.0", "application")
        ),
    )


def _resolved_plan(access: ServiceAccess) -> ModelIntegrationPlan:
    """Return a resolved plan that contributes one protocol access default."""
    return ModelIntegrationPlan(
        source="resolved_binding",
        binding_id="openai-compatible.chat-completions",
        binding_version="1.0.0",
        match=ModelIntegrationMatch(ModelTargetMatch(True, 1), TaskMatch(True, 1)),
        task_protocol_adapter=_Component(
            ComponentDescriptor("adapter", "1.0.0", "application")
        ),
        default_service_access=access,
    )


def _authorized(endpoint: str) -> _Access:
    """Return access that contains an endpoint and an explicit authorization."""
    return _Access(
        endpoint=UriValue(endpoint, True),
        authorization=_Authorization(OpenIdentifier("authorization.none")),
    )


def test_interaction_access_wins_and_client_layer_stays_unchanged() -> None:
    """Verify the four layers are resolved once without writing to the client."""
    interaction_access = _authorized("https://interaction.example.test")
    client_access = _authorized("https://client.example.test")
    binding_access = _authorized("https://binding.example.test")
    client_layer = InteractionConfigurationLayer(service_access=client_access)
    resolver = _CountingResolver()

    resolved = resolve_service_access(
        cast(ServiceAccessResolver, resolver),
        _request(),
        _resolved_plan(binding_access),
        interaction_layer=InteractionConfigurationLayer(
            service_access=interaction_access
        ),
        client_layer=client_layer,
    )

    assert resolved.endpoint == interaction_access.endpoint
    assert resolved.authorization is interaction_access.authorization
    assert resolver.calls == 1
    assert client_layer.service_access is client_access


def test_missing_access_returns_the_resolution_error() -> None:
    """Verify absent layers fail once with the stable resolution error."""
    client_layer = InteractionConfigurationLayer()
    resolver = _CountingResolver()

    error = _capture(
        lambda: resolve_service_access(
            cast(ServiceAccessResolver, resolver),
            _request(),
            _direct_plan(),
            interaction_layer=InteractionConfigurationLayer(),
            client_layer=client_layer,
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "missing_authorization"
    assert error.phase.id.value == "service_access_resolution"
    assert error.category.id.value == "invalid_request"
    assert resolver.calls == 1
    assert client_layer.service_access is None


def test_binding_default_supplies_access_when_higher_layers_are_absent() -> None:
    """Verify the integration plan is the lowest access layer."""
    binding_access = _authorized("https://binding.example.test")
    resolver = _CountingResolver()

    resolved = resolve_service_access(
        cast(ServiceAccessResolver, resolver),
        _request(),
        _resolved_plan(binding_access),
        interaction_layer=InteractionConfigurationLayer(),
        client_layer=InteractionConfigurationLayer(),
    )

    assert resolved.endpoint is binding_access.endpoint
    assert resolved.authorization is binding_access.authorization
    assert resolver.calls == 1
