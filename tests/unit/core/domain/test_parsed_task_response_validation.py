"""Composed semantic tests for ParsedTaskResponse validation."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol, cast, runtime_checkable

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationTaskResult,
    Extensions,
    JsonValue,
    MessageDocument,
    MessageElementKind,
    MessageGroup,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    ProtocolState,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
    TokenUsage,
    validate_parsed_task_response,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide a complete open TaskNodeKind for result fixtures."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Leaf or container tree composition."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide a complete MessageElementKind for conversation fixtures."""

    id: OpenIdentifier
    """Open message Kind identifier."""

    category: str
    """Open message element category."""

    composition: Literal["leaf", "container"]
    """Leaf or container tree composition."""


@runtime_checkable
class _MessageCarrier(Protocol):
    """Describe the observable message-bearing result node surface."""

    @property
    def messages(self) -> MessageDocument:
        """Return the independent MessageDocument carried by the result node."""
        # This test-only structural view avoids importing the production module's
        # private node class while keeping static access fully typed.
        ...


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Provide an application-owned task result descriptor."""

    type: OpenIdentifier
    """Open task result identity."""

    version: str | None
    """Optional task result contract version."""

    input_schema_id: str | None
    """Optional input schema identity retained by the shared shape."""

    output_schema_id: str | None
    """Optional output schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields."""


@dataclass(frozen=True, slots=True)
class _OpenResult:
    """Provide an application-owned ModelTaskResult implementation."""

    descriptor: TaskDescriptor
    """Task result identity and schema contract."""

    document: TaskDocument
    """Versioned result tree."""

    artifacts: ArtifactCatalog
    """Result-local Artifact scope."""

    metadata: Extensions
    """Portable result metadata."""

    extensions: Extensions
    """Unknown result fields."""


@dataclass(frozen=True, slots=True)
class _CustomResultNode:
    """Provide a replaceable message-bearing TaskNode for corruption tests."""

    id: str
    """Task-document-local node identity."""

    kind: TaskNodeKind
    """Open result node classification."""

    messages: MessageDocument
    """Independent conversation output carried by the test result leaf."""

    children: tuple[TaskNode, ...]
    """Ordered child nodes, empty for this leaf fixture."""

    relations: tuple[TaskRelation, ...]
    """Ordered task relations, empty for this fixture."""

    metadata: Extensions
    """Portable node metadata."""

    extensions: Extensions
    """Unknown node fields."""


_WRONG_CONVERSATION_DESCRIPTOR: TaskDescriptor = _Descriptor(
    OpenIdentifier("embedding.create"),
    None,
    None,
    None,
    MappingProxyType({}),
    MappingProxyType({}),
)


class _WrongDescriptorConversationResult(ConversationTaskResult):
    """Expose a valid but incorrect descriptor from a conversation result."""

    __slots__ = ()

    @property
    def descriptor(self) -> TaskDescriptor:
        """Return a non-conversation result descriptor for boundary testing."""
        # Only task identity changes, isolating the concrete conversation rule
        # after common descriptor semantics have already passed validation.
        return _WRONG_CONVERSATION_DESCRIPTOR


def _assert_raises(
    error_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require validation to fail with the expected type and diagnostic text."""
    # Matching stable text ensures a failure came from the intended response fact
    # rather than an unrelated fixture setup or structural Protocol access.
    try:
        action()
    except error_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {error_type.__name__} to be raised.")


def _overwrite_field(value: object, field_name: str, replacement: object) -> None:
    """Inject one impossible decoder value into a frozen test object."""
    # Controlled low-level mutation exercises defensive trust-boundary branches
    # that public constructors and static typing correctly prevent in normal use.
    object.__setattr__(value, field_name, replacement)


def _document(*, version: str = "1.0") -> TaskDocument:
    """Create one valid open result TaskDocument."""
    # An empty application-owned tree is enough for common ModelTaskResult
    # validation and remains independent from conversation-specific composition.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    return TaskDocument(version, TaskGroupNode("root", kind, ()))


def _result() -> _OpenResult:
    """Create one valid open task result with all common fields populated."""
    # Non-empty preservation channels prove the validator checks complete nested
    # semantics without closing the result type to SDK implementations.
    descriptor: TaskDescriptor = _Descriptor(
        OpenIdentifier("vendor.document_compare"),
        "1.0",
        None,
        "schema.vendor.result",
        MappingProxyType({"descriptor": True}),
        MappingProxyType({"vendor.descriptor": 1}),
    )
    return _OpenResult(
        descriptor,
        _document(),
        ArtifactCatalog(),
        MappingProxyType({"latencyClass": "interactive"}),
        MappingProxyType({"vendor.confidence": 0.95}),
    )


def _messages(
    *,
    version: str = "1.0",
    purpose: Literal["input", "output", "context", "custom"] = "output",
) -> MessageDocument:
    """Create one independently versioned conversation result document."""
    # A concrete empty output root exercises the complete MessageDocument domain
    # without introducing task-node or Artifact representations for message data.
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    return MessageDocument(
        version,
        purpose,
        MessageGroup("message-root", kind, ()),
    )


def _status(value: str = "completed") -> OutputStatus:
    """Create one valid open output status."""
    # Use the public nominal value path so response validation observes the same
    # object shape produced by a conforming protocol adapter.
    return OutputStatus(OpenIdentifier(value))


def _state(value: JsonValue = "cursor-next") -> ProtocolState:
    """Create one complete provider protocol-state value."""
    # Separate identifiers make each protocol ownership dimension independently
    # observable while the opaque state payload remains caller-selected.
    return ProtocolState(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        OpenIdentifier("state.cursor"),
        value,
    )


def test_validate_parsed_task_response_composes_all_present_facts() -> None:
    """Verify one complete open response validates without reconstruction."""
    result = _result()
    model: ModelDescriptor = NamedModel(
        "model-actual",
        family=OpenIdentifier("family.vendor"),
        version="2026-10",
        metadata={"region": "east"},
    )
    status = _status("requires_action")
    usage = TokenUsage(11, 7, 23, {"cached": 5})
    states = (_state(), _state(None))
    response = ParsedTaskResponse(
        result,
        status,
        model,
        "tool_calls",
        usage,
        states,
        {"vendor.response_id": "response-7"},
    )

    # Identity checks prove validation neither rebuilds the envelope nor replaces
    # any open nested value with a normalized SDK-owned representation.
    assert validate_parsed_task_response(response) is response
    assert response.result is result
    assert response.resolved_model is model
    assert response.status is status
    assert response.usage is usage
    assert response.protocol_state is states


def test_validate_parsed_task_response_preserves_every_absent_fact() -> None:
    """Verify validation never fills service fields from result or defaults."""
    result = _result()
    response = ParsedTaskResponse(result, _status())

    # The result descriptor is deliberately populated, yet it cannot become a
    # resolved model. Status cannot manufacture stop reason, usage, or state.
    assert validate_parsed_task_response(response) is response
    assert response.resolved_model is None
    assert response.stop_reason is None
    assert response.usage is None
    assert response.protocol_state == ()
    assert response.extensions == {}


def test_validate_parsed_task_response_accepts_conversation_output() -> None:
    """Verify a conversation result validates its independent message tree."""
    messages = _messages()
    result = ConversationTaskResult(messages)
    response = ParsedTaskResponse(result, _status())

    # The generated task tree and MessageDocument remain separate values linked
    # only by the single result leaf created by ConversationTaskResult.
    assert validate_parsed_task_response(response) is response
    assert result.messages is messages
    node = result.document.root.children[0]
    assert isinstance(node, _MessageCarrier)
    assert node.messages is messages


def test_validate_parsed_task_response_requires_concrete_envelope_and_result() -> None:
    """Verify absent required response structure is rejected, never defaulted."""
    response = ParsedTaskResponse(_result(), _status())
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(cast(ParsedTaskResponse, object())),
        "response must be a ParsedTaskResponse",
    )

    _overwrite_field(response, "result", object())
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "result must implement ModelTaskResult",
    )


def test_validate_parsed_task_response_checks_common_result_domains() -> None:
    """Verify descriptor, document, Catalog, and JSON channels are all composed."""
    invalid_cases: tuple[tuple[str, object, type[BaseException], str], ...] = (
        ("descriptor", object(), TypeError, "descriptor must implement TaskDescriptor"),
        ("document", object(), TypeError, "document must be a TaskDocument"),
        ("artifacts", object(), TypeError, "catalog must be an ArtifactCatalog"),
        (
            "metadata",
            MappingProxyType({"invalid": math.inf}),
            ValueError,
            "must be finite",
        ),
        (
            "extensions",
            cast(Extensions, {1: True}),
            TypeError,
            "result extensions keys must be strings",
        ),
    )

    # Each fresh result varies one common field so validation order cannot mask a
    # later owned domain behind an earlier corrupted fixture from another case.
    for field_name, replacement, error_type, message in invalid_cases:
        result = _result()
        _overwrite_field(result, field_name, replacement)
        response = ParsedTaskResponse(_result(), _status())
        _overwrite_field(response, "result", result)
        _assert_raises(
            error_type,
            lambda response=response: validate_parsed_task_response(response),
            message,
        )


def test_validate_parsed_task_response_checks_conversation_semantics() -> None:
    """Verify conversation messages and their canonical task binding remain valid."""
    invalid_messages = ConversationTaskResult(_messages(version=""))
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(invalid_messages, _status())
        ),
        "MessageDocument version must not be empty",
    )

    wrong_purpose = ConversationTaskResult(_messages(purpose="input"))
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(wrong_purpose, _status())
        ),
        "messages purpose must be output",
    )

    detached = ConversationTaskResult(_messages())
    _overwrite_field(detached, "_document", _document())
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(ParsedTaskResponse(detached, _status())),
        "must contain exactly one result node",
    )


def test_validate_parsed_task_response_defends_conversation_binding_shape() -> None:
    """Verify every fixed conversation result-tree binding remains authoritative."""
    wrong_descriptor = _WrongDescriptorConversationResult(_messages())
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(wrong_descriptor, _status())
        ),
        "descriptor type must be conversation.generate",
    )

    wrong_root = ConversationTaskResult(_messages())
    _overwrite_field(wrong_root.document.root, "id", "other-root")
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(wrong_root, _status())
        ),
        "document root id must be root",
    )

    wrong_node_id = ConversationTaskResult(_messages())
    id_replacement = _CustomResultNode(
        "other-result",
        _TaskKind(OpenIdentifier("task.result"), "leaf"),
        wrong_node_id.messages,
        (),
        (),
        MappingProxyType({}),
        MappingProxyType({}),
    )
    _overwrite_field(wrong_node_id.document.root, "children", (id_replacement,))
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(wrong_node_id, _status())
        ),
        "child must be the task.result node",
    )

    wrong_node_kind = ConversationTaskResult(_messages())
    kind_replacement = _CustomResultNode(
        "result",
        _TaskKind(OpenIdentifier("task.other_result"), "leaf"),
        wrong_node_kind.messages,
        (),
        (),
        MappingProxyType({}),
        MappingProxyType({}),
    )
    _overwrite_field(wrong_node_kind.document.root, "children", (kind_replacement,))
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(wrong_node_kind, _status())
        ),
        "child must be the task.result node",
    )

    missing_carrier = ConversationTaskResult(_messages())
    replacement = TaskGroupNode(
        "result",
        _TaskKind(OpenIdentifier("task.result"), "container"),
        (),
    )
    _overwrite_field(missing_carrier.document.root, "children", (replacement,))
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(missing_carrier, _status())
        ),
        "result node must carry a MessageDocument",
    )

    detached_messages = ConversationTaskResult(_messages())
    _overwrite_field(detached_messages, "messages", _messages())
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(
            ParsedTaskResponse(detached_messages, _status())
        ),
        "result node must carry the result messages",
    )


def test_validate_parsed_task_response_checks_optional_model_and_stop_reason() -> None:
    """Verify present model semantics and stop-reason storage are not bypassed."""
    invalid_model = NamedModel("")
    response = ParsedTaskResponse(_result(), _status(), invalid_model)
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(response),
        "ModelDescriptor name must not be empty",
    )

    _overwrite_field(response, "resolved_model", object())
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "resolved_model must implement ModelDescriptor or be None",
    )

    valid = ParsedTaskResponse(_result(), _status(), stop_reason="")
    assert validate_parsed_task_response(valid).stop_reason == ""
    _overwrite_field(valid, "stop_reason", 3)
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(valid),
        "stop_reason must be a string or None",
    )


def test_validate_parsed_task_response_rejects_missing_or_invalid_status() -> None:
    """Verify required status cannot be absent or carry malformed identity."""
    response = ParsedTaskResponse(_result(), _status())
    _overwrite_field(response, "status", None)
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "status must be an OutputStatus",
    )

    wrong_storage = _status()
    _overwrite_field(wrong_storage, "id", "completed")
    _overwrite_field(response, "status", wrong_storage)
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "status id must be an OpenIdentifier",
    )

    invalid_status = _status()
    _overwrite_field(invalid_status, "id", OpenIdentifier("Invalid Status"))
    _overwrite_field(response, "status", invalid_status)
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(response),
        "OpenIdentifier",
    )


def test_validate_parsed_task_response_checks_every_usage_fact() -> None:
    """Verify usage counts and provider extensions remain portable when present."""
    invalid_cases: tuple[tuple[str, object, type[BaseException], str], ...] = (
        ("input_tokens", True, TypeError, "input_tokens must be an integer or None"),
        ("output_tokens", -1, ValueError, "output_tokens must not be negative"),
        ("total_tokens", 2**53, ValueError, "interoperable safe range"),
        (
            "extensions",
            MappingProxyType({"invalid": math.nan}),
            ValueError,
            "must be finite",
        ),
    )

    # Fresh values isolate every count and extension branch while preserving the
    # other optional accounting facts exactly as the provider reported them.
    for field_name, replacement, error_type, message in invalid_cases:
        usage = TokenUsage(1, 2, 9)
        _overwrite_field(usage, field_name, replacement)
        response = ParsedTaskResponse(_result(), _status(), usage=usage)
        _assert_raises(
            error_type,
            lambda response=response: validate_parsed_task_response(response),
            message,
        )

    # A present usage value may still omit any count independently; these None
    # fields remain absent rather than being converted to zero or recomputed.
    partial = ParsedTaskResponse(_result(), _status(), usage=TokenUsage(total_tokens=9))
    assert validate_parsed_task_response(partial).usage is partial.usage

    response = ParsedTaskResponse(_result(), _status())
    _overwrite_field(response, "usage", object())
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "usage must be a TokenUsage or None",
    )


def test_validate_parsed_task_response_checks_protocol_state_collection() -> None:
    """Verify state container, members, identities, and values are all validated."""
    response = ParsedTaskResponse(_result(), _status())
    _overwrite_field(response, "protocol_state", [_state()])
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "protocol_state must be a tuple",
    )

    _overwrite_field(response, "protocol_state", (object(),))
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "protocol_state values must be ProtocolState",
    )

    wrong_storage = _state()
    _overwrite_field(wrong_storage, "service_id", "service.vendor")
    _overwrite_field(response, "protocol_state", (wrong_storage,))
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "service_id must be an OpenIdentifier",
    )

    invalid_identity = _state()
    _overwrite_field(invalid_identity, "protocol_id", OpenIdentifier("Invalid"))
    _overwrite_field(response, "protocol_state", (invalid_identity,))
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(response),
        "OpenIdentifier",
    )

    invalid_value = _state()
    _overwrite_field(invalid_value, "state_value", math.inf)
    _overwrite_field(response, "protocol_state", (invalid_value,))
    _assert_raises(
        ValueError,
        lambda: validate_parsed_task_response(response),
        "must be finite",
    )


def test_validate_parsed_task_response_checks_response_extensions() -> None:
    """Verify response-level unknown fields obey portable JSON semantics."""
    response = ParsedTaskResponse(_result(), _status())
    _overwrite_field(response, "extensions", [])
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "extensions must be a mapping",
    )

    _overwrite_field(response, "extensions", cast(Extensions, {1: True}))
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "extensions keys must be strings",
    )

    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    _overwrite_field(response, "extensions", MappingProxyType({"cycle": cyclic}))
    _assert_raises(
        TypeError,
        lambda: validate_parsed_task_response(response),
        "structurally valid JsonValue",
    )
