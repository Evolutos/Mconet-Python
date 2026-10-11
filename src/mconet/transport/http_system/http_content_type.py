"""Content-Type handling from the planned media type only."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.media_type import MediaType, parse_media_type
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.transport.http_system.http_header import HttpHeaderField

_CONTENT_TYPE_NAME = "Content-Type"
_CONTENT_TYPE_LOOKUP = "content-type"
_TOKEN_PUNCTUATION = frozenset("!#$%&'*+-.^_`|~")
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_CONTENT_TYPE_CODE = "invalid_http_content_type"
_INVALID_HTTP_CONTENT_TYPE_MESSAGE = (
    "HTTP Content-Type does not match the planned media type."
)


def apply_http_content_type(
    headers: tuple[HttpHeaderField, ...],
    media_type: MediaType,
) -> tuple[HttpHeaderField, ...]:
    """Set Content-Type from the planned media type, without inspecting a body.

    A missing field is appended from the planned type, subtype, and parameters.
    One existing field is kept when it parses as that same media type. A
    different value, an unparseable value, or more than one field is a
    conflict. Payload bytes are not an input, so they cannot change the type.

    Args:
        headers: Mapped header fields.
        media_type: Representation declared by the encoder plan.

    Returns:
        The same header tuple when one matching Content-Type is present.
        Otherwise a new tuple with the planned field appended.

    Raises:
        TypeError: If ``headers`` or ``media_type`` has an invalid shape.
        ModelInteractionError: If the existing Content-Type conflicts with the
            plan, or the plan cannot be written as one header. The stable code
            is ``invalid_http_content_type``. Media type text is omitted.
    """
    checked = _require_headers(headers)
    planned = cast(object, media_type)
    if not isinstance(planned, MediaType):
        raise TypeError("media_type must be a MediaType.")

    try:
        rendered = _render_media_type(planned)
        canonical = parse_media_type(rendered)
    except ValueError:
        raise _invalid_http_content_type_error() from None

    matches = tuple(
        field for field in checked if field.name.casefold() == _CONTENT_TYPE_LOOKUP
    )
    if len(matches) > 1:
        raise _invalid_http_content_type_error()
    if len(matches) == 1:
        # Parse the caller value instead of comparing raw spelling. A matching
        # type keeps that spelling; a different type is not replaced by a guess.
        try:
            existing = parse_media_type(matches[0].value)
        except ValueError:
            raise _invalid_http_content_type_error() from None
        if existing != canonical:
            raise _invalid_http_content_type_error()
        return checked
    return (*checked, HttpHeaderField(_CONTENT_TYPE_NAME, rendered))


def _render_media_type(media_type: MediaType) -> str:
    """Render one planned media type as a single Content-Type value.

    Args:
        media_type: Structured media type to render.

    Returns:
        The type, subtype, and parameters in their stored order.

    Raises:
        ValueError: If a token or parameter value cannot be written safely.
    """
    if not _is_token(media_type.type) or not _is_token(media_type.subtype):
        raise ValueError("Media type tokens are not sendable.")
    rendered = [f"{media_type.type}/{media_type.subtype}"]
    for name, value in media_type.parameters:
        if not _is_token(name) or not _is_sendable_parameter_value(value):
            raise ValueError("Media type parameter is not sendable.")
        if _is_token(value):
            rendered.append(f"{name}={value}")
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            rendered.append(f'{name}="{escaped}"')
    # One separator between the type and each parameter keeps the planned order.
    return "; ".join(rendered)


def _is_token(value: str) -> bool:
    """Return whether ``value`` is one non-empty HTTP token."""
    if value == "":
        return False
    return all(_is_token_character(character) for character in value)


def _is_token_character(character: str) -> bool:
    """Return whether one character belongs to the HTTP token alphabet."""
    codepoint = ord(character)
    return (
        48 <= codepoint <= 57
        or 65 <= codepoint <= 90
        or 97 <= codepoint <= 122
        or character in _TOKEN_PUNCTUATION
    )


def _is_sendable_parameter_value(value: str) -> bool:
    """Return whether a parameter value can be written without splitting a header.

    Args:
        value: Planned parameter value.

    Returns:
        Whether every character is a space or a visible ASCII character.
    """
    return all(32 <= ord(character) <= 126 for character in value)


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


def _invalid_http_content_type_error() -> ModelInteractionError:
    """Create the content-safe failure for one conflicting Content-Type.

    Returns:
        A transport error that does not include media type text.
    """
    # Media type text is omitted so a hostile planned or caller value cannot
    # enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_CONTENT_TYPE_CODE,
        message=_INVALID_HTTP_CONTENT_TYPE_MESSAGE,
    )
