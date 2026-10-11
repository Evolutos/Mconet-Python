"""Tests that protocol planning runs once and does not execute the request."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    ErrorCategory,
    Extensions,
    Headers,
    InteractionPhase,
    MediaType,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    ParsedTaskResponse,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    UriValue,
)
from mconet.core.runtime._protocol_plan_preparation import (
    prepare_protocol_execution_plan,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentDescriptor,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    ModelIntegrationPlan,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskProtocolAdapter,
    TransportRequestPlan,
    TransportResponseMetadata,
    TransportSelection,
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
    """Structural task descriptor. Planning reads it only through the adapter."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Document:
    """Placeholder task document."""

    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class _Task:
    """Structural task that completes the request surface."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request supplied to prepare_plan."""

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
class _Authorization:
    """Opaque authorization with no credential payload."""

    kind: OpenIdentifier


def _execution_plan() -> ProtocolExecutionPlan:
    """Return one immutable plan the stub adapter can hand back."""
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    return ProtocolExecutionPlan(
        transport_plan=TransportRequestPlan(
            endpoint=UriValue("https://models.example.test", True),
            path="/v1/chat/completions",
            method="POST",
            headers=Headers(),
            query=QueryParameters(),
            authorization=cast(Authorization, authorization),
            body_signing_requirement=BodySigningRequirement(),
        ),
        payload_encoder=EncoderSelection(MediaType("application", "json")),
        success_decoder=DecoderSelection(MediaType("application", "json")),
        error_decoder=DecoderSelection(MediaType("application", "json")),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def _access() -> ResolvedServiceAccess:
    """Return resolved access that carries the same authorization as the plan."""
    return ResolvedServiceAccess(
        endpoint=UriValue("https://models.example.test", True),
        authorization=_Authorization(OpenIdentifier("authorization.none")),
        headers=Headers(),
        query=QueryParameters(),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )


class _Adapter:
    """Adapter that plans once and records every other operation."""

    def __init__(self, *, fail: bool = False) -> None:
        """Store whether planning should fail."""
        self._fail = fail
        self.plan = _execution_plan()
        self.prepare_calls = 0
        self.other_calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("adapter", "1.0.0", "application")

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: object,
    ) -> bool:
        """Record a call that planning must not make."""
        del target, task, mode
        self.other_calls += 1
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: object,
    ) -> ProtocolExecutionPlan:
        """Return the prepared plan, or fail, exactly when the scheduler asks."""
        del request, access, mode
        self.prepare_calls += 1
        if self._fail:
            raise ModelInteractionError(
                category=ErrorCategory(OpenIdentifier("invalid_request")),
                phase=InteractionPhase(OpenIdentifier("protocol_planning")),
                code="invalid_protocol_plan",
                message="Planning failed.",
            )
        return self.plan

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Record a call that planning must not make."""
        del request, plan
        self.other_calls += 1
        raise AssertionError("build_request must not be called.")

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Record a call that planning must not make."""
        del response
        self.other_calls += 1
        raise AssertionError("parse_response must not be called.")

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Record a call that planning must not make."""
        del error, metadata
        self.other_calls += 1
        raise AssertionError("parse_error must not be called.")


def _integration_plan(adapter: _Adapter) -> ModelIntegrationPlan:
    """Return a direct plan that fixes the adapter under test."""
    return ModelIntegrationPlan(
        source="direct_adapter",
        binding_id=None,
        binding_version=None,
        match=None,
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
    )


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


def test_prepare_plan_is_called_once_and_other_operations_are_not() -> None:
    """Verify one scheduling call plans once and does not execute the request."""
    adapter = _Adapter()
    request = _request()
    access = _access()
    mode = _Mode(OpenIdentifier("unary"))

    prepared = prepare_protocol_execution_plan(
        request,
        access,
        mode,
        _integration_plan(adapter),
    )

    # The same plan object comes back. Request building and transport stay idle.
    assert prepared is adapter.plan
    assert adapter.prepare_calls == 1
    assert adapter.other_calls == 0
    assert prepared.transport_plan.method == "POST"


def test_planning_failure_is_not_retried() -> None:
    """Verify a planning error is raised after the single adapter call."""
    adapter = _Adapter(fail=True)

    error = _capture(
        lambda: prepare_protocol_execution_plan(
            _request(),
            _access(),
            _Mode(OpenIdentifier("unary")),
            _integration_plan(adapter),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert adapter.prepare_calls == 1
    assert adapter.other_calls == 0
