"""Structural and responsibility tests for the task protocol adapter contract."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    ErrorCategory,
    Extensions,
    Headers,
    InteractionMode,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskResult,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    QueryParameters,
    ResolvedServiceAccess,
    TaskDescriptor,
    TaskDocument,
    UriValue,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentDescriptor,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskProtocolAdapter,
    TransportOutcome,
    TransportRequestPlan,
    TransportResponseMetadata,
    TransportSelection,
)


def _empty_extensions() -> Extensions:
    """Create independent portable mappings for structural result fixtures."""
    # Fresh storage keeps test instances independent while satisfying each open
    # protocol's complete read-only extension surface.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture used only by transport planning values."""

    kind: OpenIdentifier
    """Open discriminator retained for later handler resolution."""


@dataclass(frozen=True, slots=True)
class _TaskResult:
    """Complete structural task result used by parsed-response fixtures."""

    descriptor: TaskDescriptor
    """Task contract associated with the parsed result."""

    document: TaskDocument
    """Task-specific result document returned by protocol parsing."""

    artifacts: ArtifactCatalog
    """Result-local artifact scope, empty in this contract fixture."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive result facts."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown result fields retained by the structural protocol."""


class _Adapter:
    """Ordinary class implementing every adapter method without inheritance."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        execution_plan: ProtocolExecutionPlan,
        request_plan: ProtocolRequestPlan,
        parsed_response: ParsedTaskResponse,
        parsed_error: ModelInteractionError | None,
    ) -> None:
        """Store configurable outputs and initialize an ordered call record."""
        # Exact output references make it observable that the protocol wrapper
        # performs no reconstruction, encoding, transport, or output assembly.
        self.descriptor = descriptor
        self.execution_plan = execution_plan
        self.request_plan = request_plan
        self.parsed_response = parsed_response
        self.parsed_error = parsed_error
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Record the complete selection tuple and report support."""
        # Recording only object identities proves this ordinary implementation
        # need not normalize or register target, task, or mode values.
        self.calls.append(("supports", (target, task, mode)))
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Record planning inputs and return the configured immutable plan."""
        # No credential, payload, artifact, or transport operation occurs while
        # the prebuilt plan is returned by exact identity.
        self.calls.append(("prepare_plan", (request, access, mode)))
        return self.execution_plan

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Record request mapping inputs and return the configured request plan."""
        # Returning the native plan leaves byte encoding and authorization to
        # their dedicated components rather than performing either in this stub.
        self.calls.append(("build_request", (request, plan)))
        return self.request_plan

    def parse_response(
        self,
        response: ErasedRuntimeValue,
    ) -> ParsedTaskResponse:
        """Record a decoded success value and return parsed protocol facts."""
        # ParsedTaskResponse remains task-neutral and contains no top-level output
        # fields synthesized from the original request or Runtime state.
        self.calls.append(("parse_response", (response,)))
        return self.parsed_response

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Record decoded failure inputs and return the configured mapping."""
        # The optional result lets Runtime own a deterministic fallback when this
        # adapter does not recognize a service error payload.
        self.calls.append(("parse_error", (error, metadata)))
        return self.parsed_error


class _IncompleteAdapter:
    """Component-shaped fixture intentionally missing error parsing."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid component metadata isolates the missing behavior method."""

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return support while discarding selection inputs."""
        # The incomplete fixture is never selected; deletion avoids unused input
        # ambiguity while preserving the intended method signature.
        del target, task, mode
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Remain deliberately unusable outside structural recognition."""
        # Raising makes accidental invocation explicit without adding placeholder
        # output state to this method-completeness fixture.
        del request, access, mode
        raise AssertionError("Incomplete adapter must not execute.")

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Remain deliberately unusable outside structural recognition."""
        # The class exists only to prove one missing protocol member is detected.
        del request, plan
        raise AssertionError("Incomplete adapter must not execute.")

    def parse_response(
        self,
        response: ErasedRuntimeValue,
    ) -> ParsedTaskResponse:
        """Remain deliberately unusable outside structural recognition."""
        # No result fixture is needed because runtime conformance fails earlier.
        del response
        raise AssertionError("Incomplete adapter must not execute.")


def _execution_plan() -> ProtocolExecutionPlan:
    """Build one complete unary JSON-over-HTTP execution plan."""
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    transport_plan = TransportRequestPlan(
        endpoint=UriValue("https://models.example.test", True),
        path="/v1/responses",
        method="POST",
        headers=Headers(),
        query=QueryParameters(),
        authorization=authorization,
        body_signing_requirement=BodySigningRequirement(),
    )
    media_type = MediaType("application", "json")

    # Each component choice remains explicit so the adapter result cannot hide
    # codec or transport selection behind its native payload.
    return ProtocolExecutionPlan(
        transport_plan=transport_plan,
        payload_encoder=EncoderSelection(media_type, "protocol.request"),
        success_decoder=DecoderSelection(media_type, "protocol.response"),
        error_decoder=DecoderSelection(media_type, "protocol.error"),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def _parsed_response() -> ParsedTaskResponse:
    """Build parsed service facts around one structural task result."""
    result = _TaskResult(
        descriptor=cast(TaskDescriptor, object()),
        document=cast(TaskDocument, object()),
        artifacts=ArtifactCatalog(),
    )
    # ParsedTaskResponse validates the complete structural result surface while
    # leaving concrete task document semantics to task-specific implementations.
    assert isinstance(result, ModelTaskResult)
    return ParsedTaskResponse(
        result=result,
        status=OutputStatus(OpenIdentifier("completed")),
    )


def _adapter(
    parsed_error: ModelInteractionError | None = None,
) -> tuple[_Adapter, ProtocolExecutionPlan, ProtocolRequestPlan, ParsedTaskResponse]:
    """Build one configurable ordinary adapter and all exact return values."""
    execution_plan = _execution_plan()
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.request"), {"input": "hi"})
    request_plan = ProtocolRequestPlan(payload, execution_plan)
    parsed_response = _parsed_response()
    descriptor = ComponentDescriptor("Fixture adapter", "1.0.0", "application")

    # One helper keeps contract tests focused on method behavior and identity
    # rather than repeating unrelated nested plan construction.
    return (
        _Adapter(
            descriptor,
            execution_plan,
            request_plan,
            parsed_response,
            parsed_error,
        ),
        execution_plan,
        request_plan,
        parsed_response,
    )


def _accept_adapter(adapter: TaskProtocolAdapter) -> TaskProtocolAdapter:
    """Return an adapter after crossing the statically checked protocol boundary."""
    # Pyright verifies every ordinary method signature without SDK inheritance.
    return adapter


def test_task_protocol_adapter_accepts_ordinary_structural_class() -> None:
    """Require only descriptor metadata and the five documented methods."""
    adapter, _, _, _ = _adapter()

    accepted = _accept_adapter(adapter)

    # Runtime and static recognition agree without registration, a base class,
    # generics, a component ID, or a platform-specific adapter wrapper.
    assert accepted is adapter
    assert isinstance(adapter, TaskProtocolAdapter)
    assert adapter.descriptor.name == "Fixture adapter"


def test_task_protocol_adapter_preserves_stage_inputs_and_outputs() -> None:
    """Verify every method retains its exact input and configured output values."""
    normalized_error = ModelInteractionError(
        category=ErrorCategory(OpenIdentifier("service")),
        phase=InteractionPhase(OpenIdentifier("response_parsing")),
        code="service_error",
        message="The service reported a protocol error.",
    )
    adapter, execution_plan, request_plan, parsed_response = _adapter(normalized_error)
    target = cast(ModelTarget, object())
    task = cast(TaskDescriptor, object())
    mode = cast(InteractionMode, object())
    request = cast(ModelRequest, object())
    access = cast(ResolvedServiceAccess, object())
    success = ErasedRuntimeValue(OpenIdentifier("protocol.response"), {"ok": True})
    failure = ErasedRuntimeValue(OpenIdentifier("protocol.error"), {"error": True})
    metadata = TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("service_error")),
        Headers(),
        status_code=400,
    )

    assert adapter.supports(target, task, mode)
    assert adapter.prepare_plan(request, access, mode) is execution_plan
    assert adapter.build_request(request, execution_plan) is request_plan
    assert adapter.parse_response(success) is parsed_response
    assert adapter.parse_error(failure, metadata) is normalized_error

    # Ordered records prove the adapter received every value by identity and did
    # not merge planning, encoding, authorization, transport, or parse stages.
    assert adapter.calls == [
        ("supports", (target, task, mode)),
        ("prepare_plan", (request, access, mode)),
        ("build_request", (request, execution_plan)),
        ("parse_response", (success,)),
        ("parse_error", (failure, metadata)),
    ]


def test_task_protocol_adapter_allows_unrecognized_error_payload() -> None:
    """Preserve None so Runtime can own normalized fallback error creation."""
    adapter, _, _, _ = _adapter(parsed_error=None)
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.error"), object())
    metadata = TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("service_error")),
        Headers(),
    )

    # None is distinct from throwing or inventing a service error without enough
    # protocol facts, leaving fallback category and message to Runtime policy.
    assert adapter.parse_error(payload, metadata) is None


def test_task_protocol_adapter_has_exact_synchronous_method_surface() -> None:
    """Lock method names, argument order, and synchronous mapping semantics."""
    expected_parameters = {
        "supports": ("self", "target", "task", "mode"),
        "prepare_plan": ("self", "request", "access", "mode"),
        "build_request": ("self", "request", "plan"),
        "parse_response": ("self", "response"),
        "parse_error": ("self", "error", "metadata"),
    }

    # Pure mapping methods are synchronous and expose no client, transport,
    # credential source, mutable request, monitor, or registry parameter.
    for method_name, parameters in expected_parameters.items():
        method = getattr(TaskProtocolAdapter, method_name)
        assert tuple(inspect.signature(method).parameters) == parameters
        assert not inspect.iscoroutinefunction(method)


def test_task_protocol_adapter_requires_complete_behavior_surface() -> None:
    """Reject a component that omits any required adapter operation."""
    incomplete = _IncompleteAdapter()

    # Descriptor metadata alone is insufficient; error parsing is required even
    # when a concrete adapter commonly returns None for unknown payload shapes.
    assert not isinstance(incomplete, TaskProtocolAdapter)
