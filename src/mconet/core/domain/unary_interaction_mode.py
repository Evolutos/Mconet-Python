"""Supported unary interaction-mode validation before model interaction I/O."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_request_validation import validate_model_request
from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)

_UNARY_MODE_ID = OpenIdentifier("unary")
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_UNSUPPORTED_MODE_CODE = "unsupported_interaction_mode"
_UNSUPPORTED_MODE_MESSAGE = "Only unary interaction mode is supported."


def validate_unary_interaction_mode(
    request: ModelRequest,
    mode: InteractionMode,
) -> InteractionMode:
    """Require a valid model request to use the unary interaction mode.

    Args:
        request: The normalized task-neutral request associated with the mode.
        mode: The open execution-mode identity selected by the public entry point.

    Returns:
        The exact supplied mode when its validated ID is ``unary``.

    Raises:
        TypeError: If the request, mode, or mode ID has an invalid runtime shape.
        ValueError: If request semantics or mode identifier syntax is malformed.
        ModelInteractionError: If a valid mode ID is not supported; its stable
            code is ``unsupported_interaction_mode``.

    Notes:
        Interaction mode remains separate from ModelRequest. Validating both
        values here binds a supported entry-point mode to a complete request
        without adding a mode field to the task-neutral request envelope.

        The gate performs no integration lookup, component selection, encoding,
        authorization, transport, response mapping, or other I/O work.
    """
    # Preserve request-validation precedence from the shared preparation chain.
    # Malformed target, task, access, or JSON data must not be mislabeled as an
    # otherwise valid request using an unsupported execution mode.
    validate_model_request(request)

    candidate = cast(object, mode)
    # Structural recognition admits application-owned mode implementations while
    # rejecting bare identifiers and partial objects before reading mode.id.
    if not isinstance(candidate, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")

    identifier = cast(object, candidate.id)
    # Require the nominal open identifier and its portable grammar before support
    # comparison, preserving precise type and syntax failures at their boundary.
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("InteractionMode id must be an OpenIdentifier.")
    validate_open_identifier(identifier)

    if identifier != _UNARY_MODE_ID:
        raise _unsupported_interaction_mode_error()

    # Return the exact open value for later integration and plan checks without
    # wrapping, canonicalizing, or copying application-owned mode state.
    return candidate


def _unsupported_interaction_mode_error() -> ModelInteractionError:
    """Create the normalized failure for one unsupported interaction mode."""
    # Exclude provider-controlled mode text and request data so the deterministic
    # pre-I/O failure remains safe for ordinary exception reporting and logs.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_UNSUPPORTED_MODE_CODE,
        message=_UNSUPPORTED_MODE_MESSAGE,
    )
