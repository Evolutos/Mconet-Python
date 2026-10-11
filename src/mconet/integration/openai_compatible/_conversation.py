"""Extraction of the conversation input and parameters from a task request."""

from __future__ import annotations

from mconet.core.domain import (
    ConversationInputNode,
    ConversationTaskRequest,
    ErrorCategory,
    GenerationParameters,
    GenerationParametersNode,
    InteractionPhase,
    MessageDocument,
    ModelInteractionError,
    ModelTaskRequest,
    OpenIdentifier,
    TaskNode,
)

UNSUPPORTED_TASK_REQUEST_CODE = "unsupported_task_request"
"""Stable code for a task request that is not a ConversationTaskRequest."""

_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_PROTOCOL_ADAPTATION = InteractionPhase(OpenIdentifier("protocol_adaptation"))


def conversation_input(
    task: ModelTaskRequest,
) -> tuple[MessageDocument, GenerationParameters | None]:
    """Return the input messages and optional parameters of a conversation.

    Request validation already guarantees exactly one ConversationInputNode
    and at most one GenerationParametersNode, anywhere in the task tree. This
    walk only finds them.

    Args:
        task: Task of a validated model request.

    Returns:
        The input MessageDocument and the generation parameters, or ``None``
        when the request has no parameters node.

    Raises:
        ModelInteractionError: If the task is another implementation that
            merely reports the conversation task type. Its content has no
            defined mapping, so it is not guessed.
    """
    if not isinstance(task, ConversationTaskRequest):
        raise ModelInteractionError(
            category=_UNSUPPORTED_FEATURE,
            phase=_PROTOCOL_ADAPTATION,
            code=UNSUPPORTED_TASK_REQUEST_CODE,
            message=(
                "The OpenAI-compatible chat completions protocol requires a "
                "ConversationTaskRequest."
            ),
        )

    messages: MessageDocument | None = None
    parameters: GenerationParameters | None = None
    pending: list[TaskNode] = [task.document.root]
    # Preorder with an explicit stack, matching the request validator, so the
    # nodes found are the ones validation counted.
    while pending:
        node = pending.pop()
        if isinstance(node, ConversationInputNode):
            messages = node.messages
        elif isinstance(node, GenerationParametersNode):
            parameters = node.parameters
        pending.extend(reversed(tuple(node.children)))

    if messages is None:
        # Unreachable for a validated request; kept so an unvalidated one
        # fails with a clear error instead of an attribute error later.
        raise ValueError(
            "ConversationTaskRequest must contain a ConversationInputNode."
        )
    return messages, parameters
