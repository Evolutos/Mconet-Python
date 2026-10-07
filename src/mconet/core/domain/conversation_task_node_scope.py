"""Supported TaskNode scope validation for conversation task execution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.conversation_input_node import ConversationInputNode
from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.conversation_task_request_validation import (
    validate_conversation_task_request,
)
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.generation_parameters_node import GenerationParametersNode
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.task_group_node import TaskGroupNode
from mconet.core.domain.task_node import TaskNode

_SUPPORTED_NODE_TYPES = (
    TaskGroupNode,
    ConversationInputNode,
    GenerationParametersNode,
)
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_UNSUPPORTED_TASK_NODE_CODE = "unsupported_task_node"
_UNSUPPORTED_TASK_NODE_MESSAGE = "Conversation task contains an unsupported TaskNode."


def validate_conversation_task_node_scope(
    request: ConversationTaskRequest,
) -> ConversationTaskRequest:
    """Require a valid conversation request to contain only supported nodes.

    Args:
        request: The concrete conversation task request whose tree is inspected.

    Returns:
        The exact supplied request when every node has supported execution
        semantics.

    Raises:
        TypeError: If the request or dynamically observed child storage has an
            invalid runtime shape.
        ValueError: If the request, document, message, parameters, Artifact
            scope, or JSON data violates its domain contract.
        ModelInteractionError: If any otherwise valid node has an unsupported
            concrete behavior; its stable code is ``unsupported_task_node``.

    Notes:
        General TaskDocument validation deliberately preserves application-owned
        nodes. This separate execution gate accepts standard groups, conversation
        inputs, and generation-parameter nodes only, without deleting or
        rewriting unknown values.

        Traversal and rejection perform no protocol selection, encoding,
        authorization, transport, Artifact access, or other I/O work.
    """
    # Complete request validation owns all descriptor, tree, Message, parameter,
    # Artifact, relation, and JSON semantics. Preserve those precise failures
    # before applying the narrower execution-support policy.
    validated = validate_conversation_task_request(request)
    pending: list[TaskNode] = [validated.document.root]

    # Iterative preorder avoids recursion limits and makes the first unsupported
    # node in producer order the deterministic failure point. Reversed child
    # pushes preserve each declared left-to-right sequence.
    while pending:
        node = pending.pop()
        if not isinstance(node, _SUPPORTED_NODE_TYPES):
            raise _unsupported_task_node_error()

        # Every supported production node promises immutable tuple children.
        # Recheck at the use point so untyped post-construction mutation cannot
        # change traversal membership after complete domain validation.
        children = _snapshot_supported_children(cast(object, node.children))
        pending.extend(reversed(children))

    # Return the original request and complete tree without rebuilding, filtering,
    # normalizing Kind IDs, or discarding any supported metadata and extensions.
    return validated


def _snapshot_supported_children(value: object) -> tuple[TaskNode, ...]:
    """Return immutable children from one supported production TaskNode."""
    # Standard groups and leaves store tuple membership. Lists and other open
    # Sequences belong only to custom nodes, which cannot enter this helper after
    # the nominal supported-node check above.
    if not isinstance(value, tuple):
        raise TypeError("Supported TaskNode children must be a tuple.")

    snapshot = cast(tuple[object, ...], value)
    # Defensive member validation protects traversal if untyped code replaced a
    # frozen node's child tuple after its constructor completed.
    if any(not isinstance(child, TaskNode) for child in snapshot):
        raise TypeError("Supported TaskNode children must contain TaskNode values.")
    return cast(tuple[TaskNode, ...], value)


def _unsupported_task_node_error() -> ModelInteractionError:
    """Create the normalized failure for one unsupported task node."""
    # Omit node ID, Kind, metadata, extensions, and repr so producer-controlled
    # values cannot enter logs through this deterministic pre-I/O error.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_UNSUPPORTED_TASK_NODE_CODE,
        message=_UNSUPPORTED_TASK_NODE_MESSAGE,
    )
