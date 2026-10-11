"""Safe summary of response headers."""

from __future__ import annotations

from typing import cast

from mconet.transport.http_system.http_header import HttpHeaderField

# These fields can carry credentials. They are omitted entirely; a redacted
# placeholder would still put the field name, and sometimes the value, into
# the summary.
_OMITTED_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
    }
)


def summarize_http_response_headers(
    headers: tuple[HttpHeaderField, ...],
) -> tuple[HttpHeaderField, ...]:
    """Copy response headers except credential-bearing fields.

    Authorization, Proxy-Authorization, Cookie, and Set-Cookie are omitted
    regardless of name case. Every other field keeps its position, spelling,
    and value, including repeated names. The function does not read a body or
    open a connection.

    Args:
        headers: Mapped response header fields.

    Returns:
        A new tuple containing only the fields that may appear in a summary.

    Raises:
        TypeError: If ``headers`` is not a tuple of :class:`HttpHeaderField`.
    """
    checked = _require_headers(headers)
    return tuple(
        field for field in checked if field.name.casefold() not in _OMITTED_HEADER_NAMES
    )


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
