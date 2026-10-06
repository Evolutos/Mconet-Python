"""Semantic validation for conversation task input leaf nodes."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.conversation_input_node import ConversationInputNode
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_document_validation import validate_message_document
from mconet.core.domain.task_node_validation import validate_task_node_snapshot


def validate_conversation_input_node(
    node: ConversationInputNode,
) -> ConversationInputNode:
    """Validate one conversation input and its complete nested message document.

    Args:
        node: The concrete immutable conversation input node to validate.

    Returns:
        The same node object after successful validation.

    Raises:
        TypeError: If the node, its shared TaskNode fields, or ``messages`` has an
            invalid runtime type.
        ValueError: If task leaf semantics, node data, or the nested message
            document violates its domain contract.

    Notes:
        Task relation endpoint resolution and document-wide node ID uniqueness
        remain owned by TaskDocument validation. This function fully validates
        the nested MessageDocument because it is the node's concrete payload.
    """
    candidate = cast(object, node)
    # Require the nominal leaf before shared structural validation so unrelated
    # custom TaskNode implementations cannot acquire conversation semantics.
    if not isinstance(candidate, ConversationInputNode):
        raise TypeError("node must be a ConversationInputNode.")

    validated_node, _, _ = validate_task_node_snapshot(candidate)
    # Shared validation returns its protocol type but preserves object identity;
    # the nominal check above therefore justifies restoring the concrete type.
    validated = cast(ConversationInputNode, validated_node)
    validate_conversation_input_node_fields(validated)
    return validated


def validate_conversation_input_node_fields(node: ConversationInputNode) -> None:
    """Validate fixed Kind and message fields after shared TaskNode validation."""
    kind = node.kind
    # The shared validator already narrowed Kind fields and their portable syntax.
    # This concrete node adds exact identity and leaf semantics without a registry.
    if kind.id.value != "task.input":
        raise ValueError("ConversationInputNode kind id must be task.input.")
    if kind.composition != "leaf":
        raise ValueError("ConversationInputNode kind composition must be leaf.")

    messages = cast(object, node.messages)
    # A concrete versioned document is required even when an untyped deserializer
    # bypasses the entity constructor and replaces the field with None or a group.
    if not isinstance(messages, MessageDocument):
        raise TypeError("ConversationInputNode messages must be a MessageDocument.")

    # Delegate the complete message tree, IDs, roles, content, relations, and JSON
    # rules to the Message domain rather than duplicating them in Task validation.
    validate_message_document(messages)
