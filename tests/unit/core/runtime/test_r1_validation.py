"""Tests for R1 validation scheduling before component and access resolution."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationInputNode,
    ConversationTaskBuilder,
    Extensions,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
    TextMessageContent,
)
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.runtime._r1_validation import validate_r1_interaction


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


@dataclass
class _ResolutionProbe:
    """Count component and access resolution that must wait for validation."""

    component_calls: int = 0
    access_calls: int = 0

    def resolve(self) -> None:
        """Record one later resolution of both component and access stages."""
        # Both counters move together because a failed validation must skip the
        # whole resolution pair, not only one of the two stages.
        self.component_calls += 1
        self.access_calls += 1


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural model target for public request fixtures."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode selected by a public entry."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Open task-node kind for document fixtures."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Open message-element kind for input documents."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Role:
    """Structural message role for a user text entry."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Open task descriptor that is not conversation generation."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Open task request used to prove a non-conversation type stops early."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request that can fail domain validation without a builder."""

    target: ModelTarget
    task: ModelTaskRequest
    service_access: None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _UnknownNode:
    """Valid open task node without an R1 execution behavior."""

    id: str
    kind: TaskNodeKind
    children: Sequence[TaskNode] = ()
    relations: Sequence[TaskRelation] = ()
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


def _unary() -> InteractionMode:
    """Return the only mode the R1 gate accepts."""
    return _Mode(OpenIdentifier("unary"))


def _target(service_id: str = "service.vendor") -> ModelTarget:
    """Return one structural target for a public request."""
    return _Target(
        OpenIdentifier(service_id),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )


def _messages() -> MessageDocument:
    """Return one text-only input document."""
    # A single user entry is enough for the conversation cardinality rule.
    role: MessageRole = _Role(OpenIdentifier("message.user"))
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    entry = MessageEntry(
        "message-entry",
        role,
        (TextMessageContent("text-content", "Hello"),),
    )
    return MessageDocument("1.0", "input", MessageGroup("message-root", kind, (entry,)))


def _conversation_request(*extra_nodes: TaskNode) -> ModelRequest:
    """Build a conversation request, optionally adding unsupported nodes."""
    children: tuple[TaskNode, ...] = (
        ConversationInputNode("input", _messages()),
        *extra_nodes,
    )
    document = TaskDocument(
        "1.0",
        TaskGroupNode(
            "root", _NodeKind(OpenIdentifier("task.root"), "container"), children
        ),
    )
    task = ConversationTaskBuilder(document).build()
    return ModelRequestBuilder(_target(), task).build()


def _resolve_after_validation(
    request: ModelRequest,
    mode: InteractionMode,
    probe: _ResolutionProbe,
) -> tuple[ModelRequest, InteractionMode]:
    """Resolve components and access only after R1 validation returns."""
    # The probe stands in for the later runtime stages. It must not run when
    # validation raises.
    validated = validate_r1_interaction(request, mode)
    probe.resolve()
    return validated


def test_valid_unary_conversation_is_returned_unchanged() -> None:
    """Verify a supported request passes and only then allows resolution."""
    request = _conversation_request()
    mode = _unary()
    probe = _ResolutionProbe()

    validated_request, validated_mode = _resolve_after_validation(request, mode, probe)

    # The gates accept the caller's objects. Resolution is observable only
    # because validation returned.
    assert validated_request is request
    assert validated_mode is mode
    assert probe.component_calls == 1
    assert probe.access_calls == 1


def test_invalid_request_does_not_resolve_components_or_access() -> None:
    """Verify a domain-invalid request stops before resolution."""
    request = _Request(_target(""), _open_task())
    probe = _ResolutionProbe()

    error = _capture(lambda: _resolve_after_validation(request, _unary(), probe))

    assert isinstance(error, ValueError)
    assert probe.component_calls == 0
    assert probe.access_calls == 0


def test_unsupported_task_does_not_resolve_components_or_access() -> None:
    """Verify a non-conversation task stops before resolution."""
    request = ModelRequestBuilder(_target(), _open_task()).build()
    probe = _ResolutionProbe()

    error = _capture(lambda: _resolve_after_validation(request, _unary(), probe))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_task"
    assert probe.component_calls == 0
    assert probe.access_calls == 0


def test_unsupported_mode_does_not_resolve_components_or_access() -> None:
    """Verify a non-unary mode stops before resolution."""
    request = _conversation_request()
    mode = _Mode(OpenIdentifier("server_stream"))
    probe = _ResolutionProbe()

    error = _capture(lambda: _resolve_after_validation(request, mode, probe))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_interaction_mode"
    assert probe.component_calls == 0
    assert probe.access_calls == 0


def test_open_conversation_type_does_not_resolve_components_or_access() -> None:
    """Verify a non-concrete conversation task stops before resolution."""
    task = _Task(
        _Descriptor(OpenIdentifier("conversation.generate")),
        TaskDocument(
            "1.0",
            TaskGroupNode(
                "root",
                _NodeKind(OpenIdentifier("task.root"), "container"),
                (),
            ),
        ),
        ArtifactCatalog(),
    )
    request = ModelRequestBuilder(_target(), task).build()
    probe = _ResolutionProbe()

    error = _capture(lambda: _resolve_after_validation(request, _unary(), probe))

    # The type id matches, but R1 node and message gates need the concrete
    # conversation request. Resolution still does not start.
    assert isinstance(error, TypeError)
    assert probe.component_calls == 0
    assert probe.access_calls == 0


def test_unsupported_node_does_not_resolve_components_or_access() -> None:
    """Verify an unknown task node stops before resolution."""
    unknown = _UnknownNode(
        "provider-node",
        _NodeKind(OpenIdentifier("vendor.extension"), "leaf"),
    )
    request = _conversation_request(unknown)
    probe = _ResolutionProbe()

    error = _capture(lambda: _resolve_after_validation(request, _unary(), probe))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_task_node"
    assert probe.component_calls == 0
    assert probe.access_calls == 0


def _open_task() -> ModelTaskRequest:
    """Return a valid task whose type is outside the R1 conversation scope."""
    # The common task boundary accepts this tree. The R1 type gate must still
    # reject it before component or access resolution.
    return _Task(
        _Descriptor(OpenIdentifier("vendor.document-compare")),
        TaskDocument(
            "1.0",
            TaskGroupNode(
                "root", _NodeKind(OpenIdentifier("task.root"), "container"), ()
            ),
        ),
        ArtifactCatalog(),
    )
