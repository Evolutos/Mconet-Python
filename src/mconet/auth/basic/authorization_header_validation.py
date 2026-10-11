"""Wire checks for authorization header names and values."""

from __future__ import annotations

import re
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

# RFC 9110 tchar. A blank name, a colon, and every other non-token character
# fail this pattern, including a token that merely contains one illegal mark.
_HEADER_NAME_PATTERN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_AUTHENTICATION_PHASE = InteractionPhase(OpenIdentifier("authentication"))
_INVALID_HEADER_NAME_CODE = "invalid_authorization_header_name"
_INVALID_HEADER_NAME_MESSAGE = "Authorization header name is not an HTTP token."
_INVALID_HEADER_VALUE_CODE = "invalid_authorization_header_value"
_INVALID_HEADER_VALUE_MESSAGE = (
    "Authorization header value contains a control character."
)


def validate_authorization_header_name(name: str) -> None:
    """Reject a header name that cannot be one HTTP field name.

    Blank text, a colon, and any other character outside the HTTP token
    alphabet fail with the same error. The rejected text is not copied into
    that error.

    Args:
        name: Header name supplied by an authorization decision.

    Raises:
        TypeError: If ``name`` is not a string.
        ModelInteractionError: If ``name`` is not exactly one HTTP token. The
            stable code is ``invalid_authorization_header_name``.
    """
    candidate = cast(object, name)
    if not isinstance(candidate, str):
        raise TypeError("Authorization header name must be a string.")
    if _HEADER_NAME_PATTERN.fullmatch(candidate) is None:
        raise _invalid_header_name_error()


def validate_authorization_header_value(value: str) -> None:
    """Reject a header value that contains CR, LF, or another control.

    Space and ordinary text are accepted. ASCII controls, including tab, CR,
    LF, and DEL, fail with one error. The rejected value is not copied into
    that error.

    Args:
        value: Header value, prefix, or composed authorization field value.

    Raises:
        TypeError: If ``value`` is not a string.
        ModelInteractionError: If ``value`` contains an ASCII control. The
            stable code is ``invalid_authorization_header_value``.
    """
    candidate = cast(object, value)
    if not isinstance(candidate, str):
        raise TypeError("Authorization header value must be a string.")
    # Controls would split the field or inject another header. The check is
    # on the whole value, so a legal prefix cannot hide a control in the key.
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise _invalid_header_value_error()


def _invalid_header_name_error() -> ModelInteractionError:
    """Create the stable failure for one illegal authorization header name."""
    # The name is omitted because it can contain injected field text that must
    # not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_INVALID_HEADER_NAME_CODE,
        message=_INVALID_HEADER_NAME_MESSAGE,
    )


def _invalid_header_value_error() -> ModelInteractionError:
    """Create the stable failure for one illegal authorization header value."""
    # The value is omitted because it can be the credential or an injected
    # header that must not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_INVALID_HEADER_VALUE_CODE,
        message=_INVALID_HEADER_VALUE_MESSAGE,
    )
