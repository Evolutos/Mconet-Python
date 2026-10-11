"""Safe default HTTP headers added only when the caller omitted them."""

from __future__ import annotations

from typing import cast

from mconet.transport.http_system.http_header import HttpHeaderField

_ACCEPT_NAME = "Accept"
_USER_AGENT_NAME = "User-Agent"
_ACCEPT_LOOKUP = "accept"
_USER_AGENT_LOOKUP = "user-agent"
_DEFAULT_ACCEPT = "application/json"
_DEFAULT_USER_AGENT = "mconet-sdk"


def apply_default_http_headers(
    headers: tuple[HttpHeaderField, ...],
) -> tuple[HttpHeaderField, ...]:
    """Append Accept and User-Agent when those names are absent.

    Name comparison is case-insensitive. An existing field is kept, including
    its spelling, value, and position, even when the value is empty. Missing
    defaults are appended after the caller fields in the order Accept, then
    User-Agent. The function does not add authorization, cookie, content, or
    encoding fields, and it does not open a connection.

    Args:
        headers: Mapped header fields whose names and values are already
            sendable.

    Returns:
        The same tuple when both defaults are already present. Otherwise a new
        tuple with only the missing defaults appended.

    Raises:
        TypeError: If ``headers`` is not a tuple of :class:`HttpHeaderField`.
    """
    candidate = cast(object, headers)
    if not isinstance(candidate, tuple):
        raise TypeError("headers must be a tuple.")

    present: set[str] = set()
    for field in cast(tuple[object, ...], candidate):
        if not isinstance(field, HttpHeaderField):
            raise TypeError("headers must contain HttpHeaderField values.")
        # casefold matches HTTP name equality without rewriting the stored name.
        present.add(field.name.casefold())

    missing: list[HttpHeaderField] = []
    if _ACCEPT_LOOKUP not in present:
        missing.append(HttpHeaderField(_ACCEPT_NAME, _DEFAULT_ACCEPT))
    if _USER_AGENT_LOOKUP not in present:
        missing.append(HttpHeaderField(_USER_AGENT_NAME, _DEFAULT_USER_AGENT))

    # Every element was checked above, so the original tuple can be returned
    # without copying when the caller already chose both fields.
    checked = cast(tuple[HttpHeaderField, ...], candidate)
    if not missing:
        return checked
    return (*checked, *missing)
