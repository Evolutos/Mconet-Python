"""Server-stream interaction-mode validation before model interaction I/O."""

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

_SERVER_STREAM_MODE_ID = OpenIdentifier("server_stream")
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_UNSUPPORTED_MODE_CODE = "unsupported_interaction_mode"
_UNSUPPORTED_MODE_MESSAGE = "Only server_stream interaction mode is supported."


def validate_server_stream_interaction_mode(
    request: ModelRequest,
    mode: InteractionMode,
) -> InteractionMode:
    """Require a valid model request to use the server-stream interaction mode.

    Args:
        request: The normalized task-neutral request associated with the mode.
        mode: The open execution-mode identity selected by the public entry.

    Returns:
        The exact supplied mode when its validated ID is ``server_stream``.

    Raises:
        TypeError: If the request, mode, or mode ID has an invalid runtime shape.
        ValueError: If request semantics or mode identifier syntax is malformed.
        ModelInteractionError: If a valid mode ID is not ``server_stream``. Its
            stable code is ``unsupported_interaction_mode``.

    Notes:
        Unary interaction keeps its own gate. This function is the matching
        gate for the server-stream entry, so a unary mode is rejected here
        rather than silently sent as a stream.
    """
    # Request validation stays first so a malformed envelope is not reported as
    # an unsupported mode.
    validate_model_request(request)
    candidate = cast(object, mode)
    # Structural recognition admits application-owned mode objects and rejects
    # a bare identifier before ``id`` is read.
    if not isinstance(candidate, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")
    identifier = cast(object, candidate.id)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("InteractionMode id must be an OpenIdentifier.")
    # Syntax is checked before the support comparison so a malformed id keeps
    # its own error instead of the unsupported-mode code.
    validate_open_identifier(identifier)
    if identifier != _SERVER_STREAM_MODE_ID:
        raise _unsupported_interaction_mode_error()
    # The caller's mode object is returned unchanged. Later stages compare its
    # id and must not see a replacement value.
    return candidate


def _unsupported_interaction_mode_error() -> ModelInteractionError:
    """Create the normalized failure for a mode that is not server-stream."""
    # Provider mode text and request data stay out of the message so the
    # pre-I/O failure is safe to log.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_UNSUPPORTED_MODE_CODE,
        message=_UNSUPPORTED_MODE_MESSAGE,
    )
