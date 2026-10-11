"""Response Content-Type extraction."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.media_type import MediaType, parse_media_type
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.transport.http_system.http_header import HttpHeaderField

_CONTENT_TYPE_LOOKUP = "content-type"
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_RESPONSE_MEDIA_TYPE_CODE = "invalid_http_response_media_type"
_INVALID_RESPONSE_MEDIA_TYPE_MESSAGE = "HTTP response Content-Type cannot be used."


def extract_http_response_media_type(
    headers: tuple[HttpHeaderField, ...],
) -> MediaType | None:
    """Extract one response media type, or none when Content-Type is absent.

    A single parseable field becomes its structured media type. Repeated
    fields are not chosen or joined, and an unparseable field is not replaced
    with a guessed type. The function does not read a response body.

    Args:
        headers: Mapped response header fields.

    Returns:
        The parsed media type, or ``None`` when no Content-Type field exists.

    Raises:
        TypeError: If ``headers`` is not a tuple of :class:`HttpHeaderField`.
        ModelInteractionError: If Content-Type is repeated or illegal. The
            stable code is ``invalid_http_response_media_type``. Field text is
            omitted.
    """
    checked = _require_headers(headers)
    matches = tuple(
        field for field in checked if field.name.casefold() == _CONTENT_TYPE_LOOKUP
    )
    # Absence stays absent. Selecting or concatenating several values would
    # invent a type the server did not send as one field.
    if not matches:
        return None
    if len(matches) != 1:
        raise _invalid_response_media_type_error()
    try:
        return parse_media_type(matches[0].value)
    except ValueError:
        raise _invalid_response_media_type_error() from None


def _require_headers(
    headers: tuple[HttpHeaderField, ...],
) -> tuple[HttpHeaderField, ...]:
    """Return headers after checking the tuple element type.

    Args:
        headers: Candidate response header sequence.

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


def _invalid_response_media_type_error() -> ModelInteractionError:
    """Create the content-safe failure for one unusable Content-Type.

    Returns:
        A transport error that does not include the field value.
    """
    # The field value is omitted because an illegal type can contain injected
    # text that must not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_RESPONSE_MEDIA_TYPE_CODE,
        message=_INVALID_RESPONSE_MEDIA_TYPE_MESSAGE,
    )
