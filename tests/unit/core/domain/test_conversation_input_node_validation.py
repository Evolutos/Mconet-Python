"""Semantic validation tests for ConversationInputNode values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.domain import (
    ConversationInputNode,
    JsonValue,
    MessageDocument,
    MessageElementKind,
    MessageGroup,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TaskRelation,
    validate_conversation_input_node,
    validate_task_document,
)


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide an open MessageElementKind for nested document fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined message Kind identity."""

    category: str
    """Producer-defined message grouping category."""

    composition: Literal["leaf", "container"]
    """Message tree composition checked by MessageDocument validation."""


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide an alternate TaskNodeKind for subclass corruption tests."""

    id: OpenIdentifier
    """Candidate conversation input Kind identity."""

    composition: Literal["leaf", "container"]
    """Candidate fixed leaf or invalid container composition."""


_WRONG_ID_KIND: TaskNodeKind = _TaskKind(
    OpenIdentifier("vendor.input"),
    "leaf",
)
_WRONG_COMPOSITION_KIND: TaskNodeKind = _TaskKind(
    OpenIdentifier("task.input"),
    "container",
)


class _WrongIdNode(ConversationInputNode):
    """Override only the fixed Kind identity on a concrete node subclass."""

    __slots__ = ()

    @property
    def kind(self) -> TaskNodeKind:
        """Return a portable but nonstandard conversation input Kind."""
        # The alternate leaf reaches the concrete exact-ID rule after all shared
        # TaskNode Kind checks have succeeded.
        return _WRONG_ID_KIND


class _WrongCompositionNode(ConversationInputNode):
    """Override only the fixed composition on a concrete node subclass."""

    __slots__ = ()

    @property
    def kind(self) -> TaskNodeKind:
        """Return the standard identity with an invalid container composition."""
        # Empty children make the generic container structurally valid, isolating
        # the concrete node's required leaf diagnostic.
        return _WRONG_COMPOSITION_KIND


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # A narrow boundary ensures an unrelated fixture failure cannot satisfy a
    # node- or message-specific validation expectation accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _messages(
    *,
    version: str = "1.0",
    purpose: Literal["input", "output", "context", "custom"] = "input",
    root_kind: str = "message.root",
) -> MessageDocument:
    """Create one nested message document with selected semantic fields."""
    # The concrete group is structurally valid so each override reaches the
    # intended MessageDocument version, purpose, or root rule.
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier(root_kind),
        "group",
        "container",
    )
    return MessageDocument(version, purpose, MessageGroup("root", kind, ()))


def _root(*children: ConversationInputNode) -> TaskGroupNode:
    """Create the standard task root around conversation input children."""
    # Exact child objects pass through unchanged so document-integration tests
    # observe the same nested message state used by direct validation.
    return TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        children,
    )


def _overwrite_messages(node: ConversationInputNode, value: object) -> None:
    """Replace the frozen messages field to emulate untyped deserialization."""
    # Constructor invariants normally prevent this state; object-level assignment
    # proves the Validator rechecks required payload presence at runtime.
    object.__setattr__(node, "messages", value)


def test_validator_accepts_valid_node_and_preserves_nested_document() -> None:
    """Verify successful validation returns the original node and messages."""
    messages = _messages()
    node = ConversationInputNode("conversation-input", messages)

    # Both task leaf and complete message document validation are observational;
    # neither rebuilds, normalizes, or replaces the nested document.
    assert validate_conversation_input_node(node) is node
    assert node.messages is messages
    assert node.kind.id == OpenIdentifier("task.input")
    assert node.kind.composition == "leaf"
    assert node.children == ()


def test_validator_rejects_non_conversation_node_before_field_access() -> None:
    """Verify unrelated objects cannot acquire conversation input semantics."""
    _assert_raises(
        TypeError,
        lambda: validate_conversation_input_node(cast(ConversationInputNode, object())),
        "must be a ConversationInputNode",
    )


def test_validator_delegates_shared_task_node_rules() -> None:
    """Verify common node identity, relation, and JSON rules remain centralized."""
    invalid_id = ConversationInputNode("", _messages())
    invalid_relation = TaskRelation(
        "",
        "target",
        OpenIdentifier("task.references"),
    )
    invalid_json = ConversationInputNode(
        "conversation-input",
        _messages(),
        metadata={"invalid": cast(JsonValue, ("tuple",))},
    )

    # Dedicated validation reuses the shared TaskNode boundary before inspecting
    # MessageDocument, so common diagnostics have one implementation owner.
    _assert_raises(
        ValueError,
        lambda: validate_conversation_input_node(invalid_id),
        "id must not be empty",
    )
    _assert_raises(
        ValueError,
        lambda: validate_conversation_input_node(
            ConversationInputNode(
                "conversation-input",
                _messages(),
                relations=(invalid_relation,),
            )
        ),
        "source must not be empty",
    )
    _assert_raises(
        TypeError,
        lambda: validate_conversation_input_node(invalid_json),
        "JsonValue",
    )


def test_validator_enforces_fixed_kind_identity_and_leaf_composition() -> None:
    """Verify concrete subclasses cannot reclassify the conversation input."""
    wrong_id = _WrongIdNode("conversation-input", _messages())
    wrong_composition = _WrongCompositionNode("conversation-input", _messages())

    # Generic TaskNode validation accepts both portable alternate Kinds; the
    # concrete Validator adds the exact identity and leaf semantics of this type.
    _assert_raises(
        ValueError,
        lambda: validate_conversation_input_node(wrong_id),
        "kind id must be task.input",
    )
    _assert_raises(
        ValueError,
        lambda: validate_conversation_input_node(wrong_composition),
        "kind composition must be leaf",
    )


def test_validator_rejects_missing_or_wrong_message_document() -> None:
    """Verify dynamically absent and message-element payloads fail stably."""
    missing = ConversationInputNode("conversation-input", _messages())
    wrong = ConversationInputNode("conversation-input", _messages())
    _overwrite_messages(missing, None)
    _overwrite_messages(wrong, _messages().root)

    # Both corrupted values bypass the constructor, proving runtime validation
    # requires the complete nominal MessageDocument rather than truthiness.
    for node in (missing, wrong):
        _assert_raises(
            TypeError,
            lambda node=node: validate_conversation_input_node(node),
            "messages must be a MessageDocument",
        )


def test_validator_delegates_complete_message_document_validation() -> None:
    """Verify nested version, purpose, and root errors keep Message diagnostics."""
    invalid_purpose = _messages()
    object.__setattr__(invalid_purpose, "purpose", "vendor-purpose")
    malformed: tuple[tuple[MessageDocument, str], ...] = (
        (_messages(version=""), "version must not be empty"),
        (invalid_purpose, "purpose must be input, output, context, or custom"),
        (_messages(root_kind="vendor.root"), "root kind must be message.root"),
    )

    # The Task wrapper does not translate or duplicate Message rules; the nested
    # Validator reports the original domain-specific diagnostic for each field.
    for messages, message in malformed:
        node = ConversationInputNode("conversation-input", messages)
        _assert_raises(
            ValueError,
            lambda node=node: validate_conversation_input_node(node),
            message,
        )


def test_task_document_validation_dispatches_conversation_payload_rules() -> None:
    """Verify whole-task traversal validates known concrete conversation leaves."""
    valid = ConversationInputNode("valid-input", _messages())
    invalid = ConversationInputNode("invalid-input", _messages(version=""))

    # TaskDocument traversal already owns stable node snapshots and invokes only
    # the known concrete payload fields, while custom TaskNode Kinds stay open.
    assert validate_task_document(TaskDocument("1.0", _root(valid))) is not None
    _assert_raises(
        ValueError,
        lambda: validate_task_document(TaskDocument("1.0", _root(invalid))),
        "MessageDocument version must not be empty",
    )
