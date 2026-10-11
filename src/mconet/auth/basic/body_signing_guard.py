"""Shared refusal of body signing that R1 authorization cannot apply."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_AUTHENTICATION_PHASE = InteractionPhase(OpenIdentifier("authentication"))
_UNSUPPORTED_BODY_SIGNING_CODE = "unsupported_body_signing"
_UNSUPPORTED_BODY_SIGNING_MESSAGE = (
    "This authorization cannot apply a body-signing mode."
)


def reject_unsupported_body_signing(body_signing_mode: str) -> None:
    """Fail when authorization would have to sign a body.

    R1 authorization accepts only ``none``. Every other mode fails with the
    same error before a handler reads a credential. The mode text is not
    copied into the error.

    Args:
        body_signing_mode: Mode selected for this authorization attempt.

    Raises:
        TypeError: If ``body_signing_mode`` is not a string.
        ModelInteractionError: If the mode is not ``none``. The stable code is
            ``unsupported_body_signing``.
    """
    mode = cast(object, body_signing_mode)
    if not isinstance(mode, str):
        raise TypeError("body_signing_mode must be a string.")
    if mode != "none":
        raise _unsupported_body_signing_error()


def _unsupported_body_signing_error() -> ModelInteractionError:
    """Create the stable failure for a signing mode R1 cannot apply."""
    # The mode is a caller-selected token. Leaving it out keeps every non-none
    # failure identical and keeps the text out of errors and logs.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_UNSUPPORTED_BODY_SIGNING_CODE,
        message=_UNSUPPORTED_BODY_SIGNING_MESSAGE,
    )
