"""Field, ownership, and leaf-semantics tests for ConversationInputNode values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from typing import Literal, cast

from mconet.core.domain import (
    ConversationInputNode,
    Extensions,
    JsonValue,
    MessageDocument,
    MessageElementKind,
    MessageGroup,
    OpenIdentifier,
    TaskNode,
    TaskRelation,
)


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide a complete message root Kind for document fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined message Kind identifier."""

    category: str
    """Producer-defined message grouping category."""

    composition: Literal["leaf", "container"]
    """Message tree composition retained for later validation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep the exception boundary narrow so an unrelated fixture error cannot
    # satisfy a storage-shape assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Crossing the static read-only boundary proves the runtime proxy enforces
    # the same ownership guarantee exposed by the public Mapping annotation.
    mapping["changed"] = True


def _mutate_kind_id(node: ConversationInputNode) -> None:
    """Attempt to replace the fixed Kind ID through a low-level setter."""
    # object.__setattr__ bypasses ordinary frozen guards. Failure proves the
    # storage-free shared Kind cannot be corrupted for any conversation input.
    object.__setattr__(node.kind, "id", OpenIdentifier("vendor.changed"))


def _messages(
    *,
    version: str = "1.0",
    root_kind: str = "message.root",
    composition: Literal["leaf", "container"] = "container",
) -> MessageDocument:
    """Create one message document with controllable deferred semantics."""
    # The helper uses only concrete production values while allowing entity tests
    # to prove conversation inputs preserve semantically pending documents.
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier(root_kind), "group", composition
    )
    return MessageDocument(version, "input", MessageGroup("root", kind, ()))


def test_conversation_input_node_is_fixed_leaf_with_message_document() -> None:
    """Verify the message document enters Task through one fixed leaf node."""
    messages = _messages()
    node = ConversationInputNode("conversation-input", messages)
    task_node: TaskNode = node

    # TaskNode conformance requires no base-class registration. MessageDocument
    # remains one explicit field and never becomes a child sequence.
    assert isinstance(node, TaskNode)
    assert task_node.id == "conversation-input"
    assert node.messages is messages
    assert node.kind.id == OpenIdentifier("task.input")
    assert node.kind.composition == "leaf"
    assert node.children == ()
    assert node.relations == ()
    assert node.metadata == {}
    assert node.extensions == {}

    # The shared Kind has no writable storage, so even low-level mutation cannot
    # affect this node or any later conversation input.
    _assert_raises(AttributeError, lambda: _mutate_kind_id(node), "has no setter")
    assert node.kind.id == OpenIdentifier("task.input")


def test_conversation_input_node_preserves_relations_and_mapping_ownership() -> None:
    """Verify ordered relations and caller mapping membership remain isolated."""
    first_relation = TaskRelation(
        "conversation-input",
        "parameters",
        OpenIdentifier("task.precedes"),
    )
    second_relation = TaskRelation(
        "conversation-input",
        "constraint",
        OpenIdentifier("vendor.informs"),
    )
    metadata: dict[str, JsonValue] = {"locale": "zh-CN"}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    node = ConversationInputNode(
        "conversation-input",
        _messages(),
        relations=(first_relation, second_relation),
        metadata=metadata,
        extensions=extensions,
    )

    # Relations keep caller order, top-level mapping changes do not leak in, and
    # frozen fields plus MappingProxy reject writes through public storage.
    metadata["locale"] = "en"
    extensions["other"] = False
    assert node.relations == (first_relation, second_relation)
    assert node.relations[0] is first_relation
    assert node.relations[1] is second_relation
    assert node.metadata == {"locale": "zh-CN"}
    assert node.extensions == {"vendorField": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: node.__setattr__("id", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], node.metadata)),
        "does not support item assignment",
    )


def test_conversation_input_node_constructor_exposes_only_owned_fields() -> None:
    """Verify fixed leaf, message internals, and other task data cannot be injected."""
    parameters = tuple(inspect.signature(ConversationInputNode).parameters)

    # Kind and children are fixed properties. Message roles/content stay inside
    # MessageDocument, while generation, tool, access, and protocol data stay out.
    assert parameters == (
        "id",
        "messages",
        "relations",
        "metadata",
        "extensions",
    )
    for field_name in (
        "kind",
        "children",
        "role",
        "content",
        "parameters",
        "tools",
        "authorization",
        "transport",
    ):
        assert field_name not in parameters


def test_conversation_input_node_definition_defers_semantic_validation() -> None:
    """Verify node ID and nested message semantics remain validator concerns."""
    pending_messages = _messages(
        version="",
        root_kind="vendor.pending_root",
        composition="leaf",
    )
    pending_json = cast(JsonValue, ("not", "portable"))
    node = ConversationInputNode(
        "",
        pending_messages,
        metadata={"pending": pending_json},
    )

    # Construction retains source data without normalization. Dedicated Task and
    # Message validators later attribute each semantic failure to its own domain.
    assert node.id == ""
    assert node.messages is pending_messages
    assert node.messages.version == ""
    assert node.messages.root.kind.id == OpenIdentifier("vendor.pending_root")
    assert node.messages.root.kind.composition == "leaf"
    assert node.metadata["pending"] is pending_json


def test_conversation_input_node_requires_concrete_message_document() -> None:
    """Verify a message group cannot replace the complete nested document."""
    messages = _messages()

    # MessageGroup is a tree node rather than a versioned document; accepting it
    # would erase the MessageDocument validation and metadata boundary.
    _assert_raises(
        TypeError,
        lambda: ConversationInputNode(
            "conversation-input",
            cast(MessageDocument, messages.root),
        ),
        "messages must be a MessageDocument",
    )


def test_conversation_input_node_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass immutable field contracts."""
    messages = _messages()
    relation = TaskRelation("conversation-input", "other", OpenIdentifier("task.links"))
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ConversationInputNode(cast(str, 1), messages),
            "id must be a string",
        ),
        (
            lambda: ConversationInputNode(
                "conversation-input",
                messages,
                relations=cast(tuple[TaskRelation, ...], [relation]),
            ),
            "relations must be a tuple",
        ),
        (
            lambda: ConversationInputNode(
                "conversation-input",
                messages,
                relations=cast(tuple[TaskRelation, ...], (object(),)),
            ),
            "relations must contain TaskRelation values",
        ),
        (
            lambda: ConversationInputNode(
                "conversation-input", messages, metadata=cast(Extensions, [])
            ),
            "metadata must be a mapping",
        ),
        (
            lambda: ConversationInputNode(
                "conversation-input",
                messages,
                metadata=cast(Extensions, {1: True}),
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: ConversationInputNode(
                "conversation-input",
                messages,
                extensions=cast(Extensions, "invalid"),
            ),
            "extensions must be a mapping",
        ),
    )

    # Semantic ID, nested-document, relation endpoint, and recursive JSON rules
    # stay deferred; each case here changes only one immutable storage boundary.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
