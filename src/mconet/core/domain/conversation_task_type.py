"""Supported conversation task-type validation before model interaction I/O."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.conversation_task_request_validation import (
    validate_conversation_task_request,
)
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_task_request import ModelTaskRequest
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.task_descriptor_validation import validate_task_descriptor

_CONVERSATION_TASK_TYPE = OpenIdentifier("conversation.generate")
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_UNSUPPORTED_TASK_CODE = "unsupported_task"
_UNSUPPORTED_TASK_MESSAGE = "Only conversation.generate tasks are supported."


def validate_conversation_task_type(task: ModelTaskRequest) -> ModelTaskRequest:
    """Require a valid task descriptor to identify conversation generation.

    Args:
        task: An open task request whose descriptor selects execution behavior.

    Returns:
        The exact supplied task when its validated type is
        ``conversation.generate``.

    Raises:
        TypeError: If the task or descriptor has an invalid runtime shape.
        ValueError: If descriptor or known conversation request semantics are
            malformed.
        ModelInteractionError: If a valid descriptor identifies any unsupported
            task type; its stable code is ``unsupported_task``.

    Notes:
        The check is based on the open descriptor identity, not concrete Python
        class membership. A standard :class:`ConversationTaskRequest` receives
        its complete composed validation before return. Application-owned open
        implementations remain eligible after their surrounding ModelRequest has
        crossed normal common-domain validation.

        The gate performs no protocol selection, encoding, authorization,
        transport, response mapping, or other I/O work.
    """
    candidate = cast(object, task)
    # Structural recognition preserves application-owned implementations while
    # rejecting partial objects before reading their descriptor property.
    if not isinstance(candidate, ModelTaskRequest):
        raise TypeError("task must implement ModelTaskRequest.")

    # Validate the complete open descriptor before applying support policy, so a
    # malformed type retains its precise domain failure instead of being reported
    # as a valid but unsupported task.
    descriptor = validate_task_descriptor(candidate.descriptor)
    if descriptor.type != _CONVERSATION_TASK_TYPE:
        raise _unsupported_task_error()

    # The standard concrete request owns additional Message, parameter, Artifact,
    # and JSON invariants. Reuse its sole validator rather than duplicating those
    # rules inside this narrow task-selection gate.
    if isinstance(candidate, ConversationTaskRequest):
        validate_conversation_task_request(candidate)

    # Preserve exact task identity for later node-scope and protocol checks; this
    # function never rebuilds, wraps, normalizes, or replaces caller data.
    return candidate


def _unsupported_task_error() -> ModelInteractionError:
    """Create the normalized failure for one unsupported task identity."""
    # Keep provider-controlled type text, metadata, documents, and extensions out
    # of the message so the pre-I/O failure is stable and safe for ordinary logs.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_UNSUPPORTED_TASK_CODE,
        message=_UNSUPPORTED_TASK_MESSAGE,
    )
