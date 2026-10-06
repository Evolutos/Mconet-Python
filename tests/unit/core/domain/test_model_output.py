"""Structural openness, ownership, and read-only tests for ModelOutput."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from types import MappingProxyType
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    Diagnostic,
    Extensions,
    InteractionPhase,
    ModelDescriptor,
    ModelOutput,
    ModelTarget,
    ModelTaskResult,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ProtocolState,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TokenUsage,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide a complete TaskNodeKind for output result fixtures."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Leaf or container task-tree composition."""


@dataclass(frozen=True, slots=True)
class _TaskDescriptor:
    """Provide an application-owned task result descriptor."""

    type: OpenIdentifier
    """Open task result identity."""

    version: str | None
    """Optional result contract version."""

    input_schema_id: str | None
    """Optional input schema identity retained by the common shape."""

    output_schema_id: str | None
    """Optional result schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields."""


@dataclass(frozen=True, slots=True)
class _TaskResult:
    """Provide an application-owned ModelTaskResult implementation."""

    descriptor: TaskDescriptor
    """Task result identity and schema contract."""

    document: TaskDocument
    """Versioned result tree."""

    artifacts: ArtifactCatalog
    """Result-local Artifact reference scope."""

    metadata: Extensions
    """Portable result metadata."""

    extensions: Extensions
    """Unknown result fields."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Provide an application-owned ModelTarget implementation."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected service protocol identity."""

    model: ModelDescriptor
    """Requested model descriptor retained by target ownership."""

    deployment_id: str | None
    """Optional requested service deployment identity."""

    extensions: Extensions
    """Unknown target fields."""


@dataclass(frozen=True, slots=True)
class _CustomModelOutput:
    """Provide a complete Runtime-owned ModelOutput implementation."""

    id: str | None
    """Optional assembled output identity."""

    target: ModelTarget
    """Exact target retained from the originating request."""

    resolved_model: ModelDescriptor | None
    """Optional service-reported actual model descriptor."""

    status: OutputStatus
    """Required protocol-derived output status."""

    result: ModelTaskResult
    """Task-neutral parsed model result."""

    stop_reason: str | None
    """Optional provider stop reason."""

    usage: TokenUsage | None
    """Optional provider-reported token accounting."""

    diagnostics: tuple[Diagnostic, ...]
    """Ordered immutable Runtime diagnostics."""

    protocol_state: tuple[ProtocolState, ...]
    """Ordered immutable service protocol state facts."""

    extensions: Extensions
    """Unknown assembled-output fields."""


def _target(model_name: str = "requested-model") -> ModelTarget:
    """Create one complete model target with a distinct requested model."""
    # Separate service, protocol, model, and deployment values make original
    # request routing independently observable from service resolution facts.
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel(model_name),
        "deployment-primary",
        MappingProxyType({"routingHint": "east"}),
    )


def _result() -> ModelTaskResult:
    """Create one structurally complete open task result."""
    # A provider-defined task family proves the output contract does not require
    # a concrete conversation result or add task-specific top-level projections.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    descriptor: TaskDescriptor = _TaskDescriptor(
        OpenIdentifier("vendor.document_compare"),
        "1.0",
        None,
        "schema.vendor.result",
        MappingProxyType({}),
        MappingProxyType({}),
    )
    return _TaskResult(
        descriptor,
        TaskDocument("1.0", TaskGroupNode("root", kind, ())),
        ArtifactCatalog(),
        MappingProxyType({"resultLabel": "comparison"}),
        MappingProxyType({"vendor.confidence": 0.97}),
    )


def _diagnostic() -> Diagnostic:
    """Create one Runtime-owned output diagnostic."""
    # A validation-phase observation remains distinct from service status and
    # provider protocol state in the assembled output contract.
    return Diagnostic(
        "response_warning",
        "warning",
        InteractionPhase(OpenIdentifier("validation")),
        "Response included a provider warning.",
    )


def _state() -> ProtocolState:
    """Create one service-owned protocol state fact."""
    # Independent identity dimensions and an opaque cursor demonstrate that state
    # is not a Runtime diagnostic or a convenience output projection.
    return ProtocolState(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        OpenIdentifier("state.cursor"),
        {"cursor": "next-2"},
    )


def _accept_model_output(output: ModelOutput) -> ModelOutput:
    """Return one output after crossing the static structural boundary."""
    # Pyright proves the fixture implements every exact property type while the
    # runtime Protocol check confirms that the full field surface is present.
    return output


def test_model_output_accepts_complete_structural_implementation() -> None:
    """Verify Runtime can implement output without SDK inheritance or registration."""
    target = _target()
    resolved_model: ModelDescriptor = NamedModel("actual-model", version="2026-10")
    status = OutputStatus(OpenIdentifier("completed"))
    result = _result()
    usage = TokenUsage(12, 8, 23)
    diagnostic = _diagnostic()
    state = _state()
    extensions: Extensions = MappingProxyType({"vendor.response_id": "response-9"})
    output = _CustomModelOutput(
        "output-7",
        target,
        resolved_model,
        status,
        result,
        "stop",
        usage,
        (diagnostic,),
        (state,),
        extensions,
    )

    # Exact identities prove assembly keeps every owner separate and the open
    # Protocol adds no hidden conversion, registration, or concrete base class.
    assert isinstance(output, ModelOutput)
    assert _accept_model_output(output) is output
    assert output.id == "output-7"
    assert output.target is target
    assert output.resolved_model is resolved_model
    assert output.status is status
    assert output.result is result
    assert output.stop_reason == "stop"
    assert output.usage is usage
    assert output.diagnostics == (diagnostic,)
    assert output.protocol_state == (state,)
    assert output.extensions is extensions


def test_model_output_keeps_request_target_and_resolved_model_independent() -> None:
    """Verify missing model resolution never aliases the original request target."""
    target = _target("requested-model")
    output = _CustomModelOutput(
        None,
        target,
        None,
        OutputStatus(OpenIdentifier("unknown")),
        _result(),
        None,
        None,
        (),
        (),
        MappingProxyType({}),
    )

    # The requested model remains reachable only through target. None records that
    # the service did not report an actual model and cannot be filled from target.
    assert isinstance(output, ModelOutput)
    assert output.id is None
    assert output.target is target
    assert output.target.model.name == "requested-model"
    assert output.resolved_model is None
    assert output.stop_reason is None
    assert output.usage is None
    assert output.diagnostics == ()
    assert output.protocol_state == ()


def test_model_output_protocol_exposes_exact_read_only_field_surface() -> None:
    """Verify all top-level output fields are properties without setters."""
    properties = {
        name: value
        for name, value in vars(ModelOutput).items()
        if isinstance(value, property)
    }

    # Exact membership prevents transport, access, request, task projections, or
    # mutable controls from leaking into the assembled output data boundary.
    assert tuple(properties) == (
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
    assert all(
        value.fset is None and value.fdel is None for value in properties.values()
    )
    for field_name in (
        "request",
        "service_access",
        "transport",
        "response_metadata",
        "messages",
        "text",
        "error",
    ):
        assert field_name not in properties


def test_model_output_implementation_can_enforce_runtime_immutability() -> None:
    """Verify a conforming frozen output prevents post-assembly field replacement."""
    output = _CustomModelOutput(
        None,
        _target(),
        None,
        OutputStatus(OpenIdentifier("completed")),
        _result(),
        None,
        None,
        (),
        (),
        MappingProxyType({}),
    )

    # The protocol exposes no setter, and the representative Runtime-owned value
    # also rejects low-level public assignment after all owners have been combined.
    try:
        output.__setattr__("status", OutputStatus(OpenIdentifier("failed")))
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Expected ModelOutput implementation to be frozen.")
    assert str(output.status) == "completed"


def test_model_output_requires_the_complete_owned_field_surface() -> None:
    """Verify parsed facts alone cannot masquerade as an assembled output."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteOutput:
        """Intentionally omit target, diagnostics, and all sibling output facts."""

        result: ModelTaskResult
        """A parsed task result without complete Runtime assembly ownership."""

    incomplete = _IncompleteOutput(_result())

    # Runtime recognition requires all ten fields, so a result or parsed response
    # cannot accidentally cross the public ModelOutput boundary before assembly.
    assert not isinstance(incomplete, ModelOutput)
