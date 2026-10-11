"""Content-Length handling for one complete HTTP body."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.transport.http_system.http_header import HttpHeaderField

_CONTENT_LENGTH_NAME = "Content-Length"
_CONTENT_LENGTH_LOOKUP = "content-length"
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_CONTENT_LENGTH_CODE = "invalid_http_content_length"
_INVALID_HTTP_CONTENT_LENGTH_MESSAGE = "HTTP Content-Length does not match the body."


def apply_http_content_length(
    headers: tuple[HttpHeaderField, ...],
    body: bytes,
) -> tuple[HttpHeaderField, ...]:
    """Set Content-Length from the body, or keep one exact existing value.

    A missing field is appended as the decimal byte length. One existing field
    is kept, with its original spelling, only when its value is that same
    decimal text. Zero, several fields, or any other value is a conflict. The
    function does not read a media type or open a connection.

    Args:
        headers: Mapped header fields.
        body: Body octets whose length is authoritative.

    Returns:
        The same header tuple when one matching Content-Length is present.
        Otherwise a new tuple with the missing field appended.

    Raises:
        TypeError: If ``headers`` or ``body`` has an invalid shape.
        ModelInteractionError: If the existing Content-Length conflicts with
            the body. The stable code is ``invalid_http_content_length``. The
            field value is omitted.
    """
    checked = _require_headers(headers)
    payload = cast(object, body)
    if not isinstance(payload, bytes):
        raise TypeError("body must be bytes.")

    length = str(len(payload))
    matches = tuple(
        field for field in checked if field.name.casefold() == _CONTENT_LENGTH_LOOKUP
    )
    # Several fields are a conflict even when each text matches, because the
    # request would no longer have one length.
    if len(matches) > 1 or (len(matches) == 1 and matches[0].value != length):
        raise _invalid_http_content_length_error()
    if len(matches) == 1:
        return checked
    return (*checked, HttpHeaderField(_CONTENT_LENGTH_NAME, length))


def _require_headers(
    headers: tuple[HttpHeaderField, ...],
) -> tuple[HttpHeaderField, ...]:
    """Return headers after checking the tuple element type.

    Args:
        headers: Candidate mapped header sequence.

    Returns:
        The same tuple when every element is an :class:`HttpHeaderField`.

    Raises:
        TypeError: If ``headers`` is not that tuple.
    """
    candidate = cast(object, headers)
    if not isinstance(candidate, tuple):
        raise TypeError("headers must be a tuple.")
    for field in cast(tuple[object, ...], candidate):
        if not isinstance(field, HttpHeaderField):
            raise TypeError("headers must contain HttpHeaderField values.")
    return cast(tuple[HttpHeaderField, ...], candidate)


def _invalid_http_content_length_error() -> ModelInteractionError:
    """Create the content-safe failure for one conflicting Content-Length.

    Returns:
        A transport error that does not include the field value.
    """
    # The supplied length can contain injected header text, so the public
    # failure names the conflict without repeating that value.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_CONTENT_LENGTH_CODE,
        message=_INVALID_HTTP_CONTENT_LENGTH_MESSAGE,
    )
