"""HTTP header mapping that preserves repeated fields and name spelling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.header_field import HeaderField
from mconet.core.domain.headers import Headers
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

# RFC 9110 tchar. The name is compared later without case, but this mapping
# does not rewrite the caller's spelling into one canonical form.
_HEADER_NAME_PATTERN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_HEADER_CODE = "invalid_http_header"
_INVALID_HTTP_HEADER_MESSAGE = "HTTP header cannot be sent."


@dataclass(frozen=True, slots=True)
class HttpHeaderField:
    """One header field ready for the system HTTP request.

    Repeated names stay separate. ``name`` keeps the spelling supplied by the
    caller.
    """

    name: str
    """Header field name in its original spelling."""

    value: str
    """Header field value with no added trimming or encoding."""

    def __post_init__(self) -> None:
        """Require a token name and a value without CR or LF."""
        name = cast(object, self.name)
        value = cast(object, self.value)
        if not isinstance(name, str):
            raise TypeError("HttpHeaderField name must be a string.")
        if not isinstance(value, str):
            raise TypeError("HttpHeaderField value must be a string.")
        # Construction is another entry point, so it uses the same wire rules
        # as mapping. The failure text does not repeat the rejected field.
        if not _is_sendable_header(name, value):
            raise ValueError("HttpHeaderField name or value cannot be sent.")


def map_http_headers(headers: Headers) -> tuple[HttpHeaderField, ...]:
    """Map ordered header fields without merging repeats or changing case.

    Each input field becomes one output field in the same position. Names that
    differ only by case remain separate fields with their original spelling.
    The function does not add ``Accept`` or ``User-Agent``, trim values, read
    a URL or body, or open a connection.

    Args:
        headers: Ordered protocol-neutral header fields.

    Returns:
        Wire fields in the same order, with the original name spelling.

    Raises:
        TypeError: If ``headers`` or a stored field has an invalid shape.
        ModelInteractionError: If a name is not a token or a value contains a
            control character. The stable code is ``invalid_http_header``.
            Field text is omitted.
    """
    candidate = cast(object, headers)
    if not isinstance(candidate, Headers):
        raise TypeError("headers must be Headers.")

    values = cast(object, candidate.values)
    if not isinstance(values, tuple):
        raise TypeError("Headers values must be a tuple.")

    mapped: list[HttpHeaderField] = []
    for field in cast(tuple[object, ...], values):
        if not isinstance(field, HeaderField):
            raise TypeError("Headers values must contain HeaderField values.")
        name = cast(object, field.name)
        value = cast(object, field.value)
        if not isinstance(name, str) or not isinstance(value, str):
            raise TypeError("HeaderField name and value must be strings.")
        # Reject before copying so a CR/LF value cannot become a second field.
        if not _is_sendable_header(name, value):
            raise _invalid_http_header_error()
        mapped.append(HttpHeaderField(name, value))
    return tuple(mapped)


def _is_sendable_header(name: str, value: str) -> bool:
    """Return whether one name and value can be written as a single field.

    Args:
        name: Candidate header name.
        value: Candidate header value.

    Returns:
        Whether ``name`` is one token and ``value`` contains no ASCII controls.
    """
    if _HEADER_NAME_PATTERN.fullmatch(name) is None:
        return False
    # Space is a normal field-value character. ASCII controls, including CR
    # and LF, would split the header block.
    return all(ord(character) >= 32 and ord(character) != 127 for character in value)


def _invalid_http_header_error() -> ModelInteractionError:
    """Create the content-safe failure for one unsendable header.

    Returns:
        A transport error that does not include the header name or value.
    """
    # Field text is omitted because a value can carry a credential or an
    # injected header that must not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_HEADER_CODE,
        message=_INVALID_HTTP_HEADER_MESSAGE,
    )
