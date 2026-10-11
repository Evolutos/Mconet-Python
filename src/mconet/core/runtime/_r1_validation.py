"""Runtime scheduling for the R1 text-unary validation gates."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from mconet.core.domain.artifact_catalog_scope import (
    validate_empty_artifact_catalog_scope,
)
from mconet.core.domain.conversation_input_node import ConversationInputNode
from mconet.core.domain.conversation_task_node_scope import (
    validate_conversation_task_node_scope,
)
from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.conversation_task_type import validate_conversation_task_type
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.message_content_scope import (
    validate_text_message_content_scope,
)
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.task_node import TaskNode
from mconet.core.domain.unary_interaction_mode import validate_unary_interaction_mode
from mconet.core.runtime._public_input_normalization import normalize_public_input


def validate_r1_interaction(
    request: ModelRequest,
    mode: InteractionMode,
) -> tuple[ModelRequest, InteractionMode]:
    """Run the R1 gates and return the same request and mode.

    The gates run in a fixed order: public-input normalization, conversation
    task type, unary mode, supported task nodes, an empty artifact catalog, and
    text-only message content. The first failure raises and this function
    returns nothing. It has no component resolver, service-access resolver, or
    client argument, so a failed gate cannot continue into those stages.

    Args:
        request: The public model request for one interaction.
        mode: The interaction mode selected by the public entry.

    Returns:
        The same request and mode objects when every R1 gate accepts them.

    Raises:
        TypeError: If a request, mode, or nested value has an invalid type.
        ValueError: If domain semantics are invalid.
        ModelInteractionError: If the request or mode is outside the R1 text
            unary scope.
    """
    # Domain normalization is the first gate. A malformed envelope must fail
    # before task, mode, message, or artifact policy runs.
    normalized = normalize_public_input(request)
    task = validate_conversation_task_type(normalized.task)
    # Mode stays outside the request envelope. Reject a non-unary mode before
    # walking the task tree.
    validated_mode = validate_unary_interaction_mode(normalized, mode)
    # The remaining gates inspect the concrete conversation tree. An open task
    # that only reuses the conversation type id has no supported node vocabulary.
    if not isinstance(task, ConversationTaskRequest):
        raise TypeError("R1 validation requires a ConversationTaskRequest.")

    scoped = validate_conversation_task_node_scope(task)
    # Artifact and message policy stay explicit at this stage. Nested request
    # validation may already have applied them; repeating the same gates keeps
    # the R1 schedule intact if that nesting changes.
    validate_empty_artifact_catalog_scope(scoped.artifacts)
    _validate_message_content(scoped)
    return normalized, validated_mode


def _validate_message_content(request: ConversationTaskRequest) -> None:
    """Require every conversation input document to contain only text."""
    pending: list[TaskNode] = [request.document.root]
    # Preorder keeps the first unsupported content item in producer order.
    # The walk reads message structure only and does not resolve components,
    # access, or artifact bytes.
    while pending:
        node = pending.pop()
        if isinstance(node, ConversationInputNode):
            validate_text_message_content_scope(node.messages)
        pending.extend(reversed(_task_children(node)))


def _task_children(node: TaskNode) -> tuple[TaskNode, ...]:
    """Return one stable child tuple for the message-scope walk."""
    children = cast(object, node.children)
    # Strings and byte buffers are sequences but are not task-node membership.
    if not isinstance(children, Sequence) or isinstance(
        children, (str, bytes, bytearray)
    ):
        raise TypeError("TaskNode children must be a sequence.")
    snapshot = tuple(cast(Sequence[object], children))
    if any(not isinstance(child, TaskNode) for child in snapshot):
        raise TypeError("TaskNode children must contain TaskNode values.")
    return cast(tuple[TaskNode, ...], snapshot)
