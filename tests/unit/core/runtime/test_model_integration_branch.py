"""Tests for joining the direct and resolved integration branches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    CompatibilityPolicy,
    Extensions,
    InteractionMode,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
)
from mconet.core.runtime._model_integration_branch import resolve_model_integration
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ModelTargetMatch,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskMatch,
    TaskProtocolAdapter,
    TransportResponseMetadata,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep one fixture from mutating another fixture's fields.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural model target."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Structural task descriptor."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Document:
    """Placeholder task document. The join does not read it."""

    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class _Task:
    """Structural task forwarded through the selected branch."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request used by both branches."""

    target: ModelTarget
    task: ModelTaskRequest
    service_access: ServiceAccess | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Component:
    """Runtime component stored as the resolved plan's adapter."""

    descriptor: ComponentDescriptor


class _Adapter:
    """Explicit adapter that supports the request and counts other calls."""

    def __init__(self) -> None:
        """Start with no recorded calls."""
        self.supports_calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("direct-adapter", "1.0.0", "application")

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Accept the request."""
        del target, task, mode
        self.supports_calls += 1
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Fail if the join plans the request."""
        del request, access, mode
        raise AssertionError("prepare_plan must not be called.")

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Fail if the join builds a protocol request."""
        del request, plan
        raise AssertionError("build_request must not be called.")

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Fail if the join parses a response."""
        del response
        raise AssertionError("parse_response must not be called.")

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Fail if the join parses an error."""
        del error, metadata
        raise AssertionError("parse_error must not be called.")


class _Resolver:
    """Resolver that records calls and returns one resolved plan."""

    def __init__(self, plan: ModelIntegrationPlan) -> None:
        """Store the plan and start with no calls."""
        self._plan = plan
        self.calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("resolver", "1.0.0", "application")

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Count one resolve call and return the prepared plan."""
        del target, task, mode, policy
        self.calls += 1
        return self._plan


def _request() -> _Request:
    """Return one structural request."""
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
    )


def _resolved_plan() -> ModelIntegrationPlan:
    """Return one resolved-binding plan."""
    return ModelIntegrationPlan(
        source="resolved_binding",
        binding_id="openai-compatible.chat-completions",
        binding_version="1.0.0",
        match=ModelIntegrationMatch(ModelTargetMatch(True, 1), TaskMatch(True, 1)),
        task_protocol_adapter=_Component(
            ComponentDescriptor("adapter", "1.0.0", "application")
        ),
    )


def test_explicit_adapter_is_the_only_plan_and_skips_the_resolver() -> None:
    """Verify the join keeps the direct plan and does not call the resolver."""
    adapter = _Adapter()
    resolver = _Resolver(_resolved_plan())

    plan = resolve_model_integration(
        cast(TaskProtocolAdapter, adapter),
        cast(ModelIntegrationResolver, resolver),
        _request(),
        _Mode(OpenIdentifier("unary")),
        CompatibilityPolicy(OpenIdentifier("compatible")),
    )

    assert plan.source == "direct_adapter"
    assert plan.task_protocol_adapter is adapter
    assert adapter.supports_calls == 1
    assert resolver.calls == 0


def test_absent_adapter_keeps_only_the_resolved_plan() -> None:
    """Verify the join keeps the resolver plan when no adapter is injected."""
    prepared = _resolved_plan()
    resolver = _Resolver(prepared)

    plan = resolve_model_integration(
        None,
        cast(ModelIntegrationResolver, resolver),
        _request(),
        _Mode(OpenIdentifier("unary")),
        CompatibilityPolicy(OpenIdentifier("strict")),
    )

    assert plan is prepared
    assert plan.source == "resolved_binding"
    assert resolver.calls == 1
