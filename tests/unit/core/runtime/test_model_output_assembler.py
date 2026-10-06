"""Ownership and validation tests for internal ModelOutput assembly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    Diagnostic,
    Extensions,
    InteractionPhase,
    ModelDescriptor,
    ModelOutput,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    ModelTaskResult,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    ProtocolState,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TokenUsage,
)
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide a complete TaskNodeKind for request and result fixtures."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Leaf or container task-tree composition."""


@dataclass(frozen=True, slots=True)
class _TaskDescriptor:
    """Provide one application-owned task descriptor."""

    type: OpenIdentifier
    """Open task identity."""

    version: str | None
    """Optional task contract version."""

    input_schema_id: str | None
    """Optional task input schema identity."""

    output_schema_id: str | None
    """Optional task output schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields."""


@dataclass(frozen=True, slots=True)
class _TaskValue:
    """Provide the shared structural fields of request and result tasks."""

    descriptor: TaskDescriptor
    """Task identity and schema contract."""

    document: TaskDocument
    """Versioned task tree."""

    artifacts: ArtifactCatalog
    """Task-local Artifact reference scope."""

    metadata: Extensions
    """Portable task metadata."""

    extensions: Extensions
    """Unknown task fields."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Provide one application-owned ModelTarget implementation."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected interaction protocol identity."""

    model: ModelDescriptor
    """Requested model descriptor."""

    deployment_id: str | None
    """Optional requested deployment identity."""

    extensions: Extensions
    """Unknown target fields."""


@dataclass(frozen=True, slots=True)
class _Request:
    """Provide a complete application-owned ModelRequest implementation."""

    target: ModelTarget
    """Original request model target."""

    task: ModelTaskRequest
    """Task request carried by the interaction."""

    service_access: ServiceAccess | None
    """Optional request-level access override."""

    metadata: Extensions
    """Portable request metadata."""

    extensions: Extensions
    """Unknown request fields."""


def _task_value(task_type: str) -> _TaskValue:
    """Create one structurally complete request or result task value."""
    # Request and result protocols intentionally share common shape while the
    # caller assigns each fresh object to exactly one ownership role.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    descriptor: TaskDescriptor = _TaskDescriptor(
        OpenIdentifier(task_type),
        "1.0",
        "schema.vendor.input",
        "schema.vendor.output",
        MappingProxyType({}),
        MappingProxyType({}),
    )
    return _TaskValue(
        descriptor,
        TaskDocument("1.0", TaskGroupNode("root", kind, ())),
        ArtifactCatalog(),
        MappingProxyType({"taskLabel": task_type}),
        MappingProxyType({}),
    )


def _target(model_name: str = "requested-model") -> ModelTarget:
    """Create one valid original request target."""
    # Distinct target dimensions let assembly prove it retains the exact request
    # object rather than recreating routing from parsed service facts.
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel(model_name),
        "deployment-primary",
        MappingProxyType({"routingHint": "east"}),
    )


def _request(target: ModelTarget | None = None) -> ModelRequest:
    """Create one complete request around the selected target fixture."""
    # Access remains explicitly absent because output assembly neither resolves
    # access nor copies request metadata, task data, or extensions into output.
    task: ModelTaskRequest = _task_value("vendor.request")
    return _Request(
        _target() if target is None else target,
        task,
        None,
        MappingProxyType({"requestLabel": "one"}),
        MappingProxyType({"requestExtension": True}),
    )


def _response(
    *,
    resolved_model: ModelDescriptor | None = None,
    status: str = "completed",
    stop_reason: str | None = None,
    usage: TokenUsage | None = None,
    protocol_state: tuple[ProtocolState, ...] = (),
    extensions: Extensions | None = None,
) -> ParsedTaskResponse:
    """Create one complete parsed response with caller-selected optional facts."""
    # A fresh open result separates response task ownership from the request task;
    # defaults express genuinely absent service fields without inferred values.
    result: ModelTaskResult = _task_value("vendor.result")
    return ParsedTaskResponse(
        result,
        OutputStatus(OpenIdentifier(status)),
        resolved_model,
        stop_reason,
        usage,
        protocol_state,
        MappingProxyType({}) if extensions is None else extensions,
    )


def _diagnostic(code: str) -> Diagnostic:
    """Create one immutable Runtime diagnostic with stable ordering identity."""
    # Distinct codes allow tuple order to be observed without coupling diagnostics
    # to service status, stop reason, protocol state, or result metadata.
    return Diagnostic(
        code,
        "warning",
        InteractionPhase(OpenIdentifier("validation")),
        "Runtime observation.",
    )


def _state(value: str) -> ProtocolState:
    """Create one parsed service protocol state fact."""
    # State remains service-owned and ordered independently from Runtime diagnostic
    # collection during final output assembly.
    return ProtocolState(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        OpenIdentifier("state.cursor"),
        value,
    )


def _assert_raises(
    error_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require a zero-argument callable to raise one stable assembly diagnostic."""
    # A narrow exception boundary keeps failures attributable to the intended
    # assembly input while avoiding a third-party matcher dependency.
    try:
        action()
    except error_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {error_type.__name__} to be raised.")


def test_model_output_assembler_transfers_each_owner_exactly_once() -> None:
    """Verify request, service, and Runtime facts retain exact independent identity."""
    target = _target()
    request = _request(target)
    resolved_model: ModelDescriptor = NamedModel("actual-model", version="2026-10")
    usage = TokenUsage(12, 8, 25)
    states = (_state("first"), _state("second"))
    extensions: Extensions = MappingProxyType({"vendor.response_id": "response-8"})
    response = _response(
        resolved_model=resolved_model,
        status="requires_action",
        stop_reason="tool_calls",
        usage=usage,
        protocol_state=states,
        extensions=extensions,
    )
    diagnostics = (_diagnostic("warning.first"), _diagnostic("warning.second"))

    output = ModelOutputAssembler().assemble(
        request,
        response,
        diagnostics,
        output_id="output-4",
    )

    # No source is rebuilt or merged: each output field points to its one
    # authoritative input, including both ordered immutable tuple snapshots.
    assert isinstance(output, ModelOutput)
    assert output.id == "output-4"
    assert output.target is target
    assert output.resolved_model is resolved_model
    assert output.status is response.status
    assert output.result is response.result
    assert output.stop_reason is response.stop_reason
    assert output.usage is usage
    assert output.diagnostics is diagnostics
    assert output.protocol_state is states
    assert output.extensions is response.extensions
    assert output.extensions is not extensions


def test_model_output_assembler_preserves_all_absent_service_facts() -> None:
    """Verify request model and defaults never fill missing parsed fields."""
    target = _target("requested-model")
    response = _response(status="unknown")
    diagnostics: tuple[Diagnostic, ...] = ()

    output = ModelOutputAssembler().assemble(
        _request(target),
        response,
        diagnostics,
    )

    # The original target remains present, but its requested model cannot become
    # a resolved service model or generate stop reason, usage, state, or an ID.
    assert output.id is None
    assert output.target is target
    assert output.target.model.name == "requested-model"
    assert output.resolved_model is None
    assert output.stop_reason is None
    assert output.usage is None
    assert output.diagnostics is diagnostics
    assert output.protocol_state == ()
    assert output.extensions == {}


def test_model_output_assembler_validates_published_target_and_response() -> None:
    """Verify invalid request target or parsed facts fail before output creation."""
    invalid_target = _target()
    object.__setattr__(invalid_target.model, "name", "")
    _assert_raises(
        ValueError,
        lambda: ModelOutputAssembler().assemble(
            _request(invalid_target),
            _response(),
            (),
        ),
        "ModelDescriptor name must not be empty",
    )

    invalid_response = _response(resolved_model=NamedModel(""))
    _assert_raises(
        ValueError,
        lambda: ModelOutputAssembler().assemble(
            _request(),
            invalid_response,
            (),
        ),
        "ModelDescriptor name must not be empty",
    )


def test_model_output_assembler_rejects_invalid_outer_inputs() -> None:
    """Verify assembly requires complete request, frozen diagnostics, and ID shape."""
    assembler = ModelOutputAssembler()
    request = _request()
    response = _response()
    diagnostic = _diagnostic("warning")
    invalid_cases = (
        (
            lambda: assembler.assemble(
                cast(ModelRequest, object()),
                response,
                (),
            ),
            "request must implement ModelRequest",
        ),
        (
            lambda: assembler.assemble(
                request,
                response,
                cast(tuple[Diagnostic, ...], [diagnostic]),
            ),
            "diagnostics must be a tuple",
        ),
        (
            lambda: assembler.assemble(
                request,
                response,
                cast(tuple[Diagnostic, ...], (object(),)),
            ),
            "diagnostics must contain Diagnostic values",
        ),
        (
            lambda: assembler.assemble(
                request,
                response,
                (),
                output_id=cast(str, 7),
            ),
            "output_id must be a string or None",
        ),
    )

    # Each case changes one ownership boundary and must fail without returning a
    # partially assembled object or coercing the supplied representation.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)


def test_model_output_assembler_creates_frozen_exact_internal_shape() -> None:
    """Verify the Runtime value is immutable and contains only ModelOutput fields."""
    output = ModelOutputAssembler().assemble(_request(), _response(), ())

    # Dataclass inspection observes the private value without depending on its
    # class name or exporting that implementation from the runtime package.
    output_slots = cast(tuple[str, ...], vars(type(output))["__slots__"])
    assert output_slots == (
        "id",
        "target",
        "resolved_model",
        "status",
        "result",
        "stop_reason",
        "usage",
        "diagnostics",
        "protocol_state",
        "extensions",
    )
    try:
        output.__setattr__("id", "changed")
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Expected assembled ModelOutput to be frozen.")


def test_model_output_assembler_remains_internal_to_runtime() -> None:
    """Verify no assembler or concrete output leaks through public package exports."""
    import mconet.core.domain
    import mconet.core.runtime

    # Business callers consume ModelOutput while Core Runtime owns its official
    # construction path and private concrete value implementation.
    assert "ModelOutputAssembler" not in mconet.core.domain.__all__
    assert "ModelOutputAssembler" not in mconet.core.runtime.__all__
    assert "_AssembledModelOutput" not in mconet.core.runtime.__all__
