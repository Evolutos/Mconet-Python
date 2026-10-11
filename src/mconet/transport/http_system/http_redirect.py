"""Header policy for one HTTP redirect."""

from __future__ import annotations

from typing import cast

from mconet.transport.http_system.http_header import HttpHeaderField
from mconet.transport.http_system.http_url import HttpBaseUrl

_HTTP_SCHEME = "http"
_HTTPS_SCHEME = "https"
_HTTP_DEFAULT_PORT = "80"
_HTTPS_DEFAULT_PORT = "443"
# Credential and signature fields. A cross-origin redirect must not carry
# them. Names are compared case-insensitively. A name ending in "-signature"
# is a signature field even when a vendor prefix differs.
_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "signature",
        "signature-input",
    }
)
_SIGNATURE_SUFFIX = "-signature"


def headers_for_http_redirect(
    current: HttpBaseUrl,
    target: HttpBaseUrl,
    headers: tuple[HttpHeaderField, ...],
) -> tuple[HttpHeaderField, ...]:
    """Return the headers that may be sent to a redirect target.

    The same origin keeps every field, including authorization and signature
    fields. A different scheme, host, or non-default port removes
    authorization, cookie, and signature fields and keeps every other field
    in its original order and spelling. Default ports 80 and 443 do not by
    themselves make a new origin. The function does not follow the redirect,
    change the method, or open a connection.

    Args:
        current: Absolute address of the request that received the redirect.
        target: Absolute address the redirect would send next.
        headers: Header fields prepared for the current request.

    Returns:
        The original tuple for the same origin, or when no sensitive field is
        present. Otherwise a new tuple of the fields that may be forwarded.

    Raises:
        TypeError: If an address is not an :class:`HttpBaseUrl`, or
            ``headers`` is not a tuple of :class:`HttpHeaderField`.
    """
    current_url = _require_base_url(current, "current")
    target_url = _require_base_url(target, "target")
    checked = _require_headers(headers)
    if _origin(current_url) == _origin(target_url):
        return checked

    forwarded = tuple(
        field for field in checked if not _is_sensitive_header(field.name)
    )
    # No sensitive field was present, so the caller's tuple is already safe.
    if len(forwarded) == len(checked):
        return checked
    return forwarded


def _require_base_url(url: HttpBaseUrl, label: str) -> HttpBaseUrl:
    """Return one redirect address after checking its type.

    Args:
        url: Candidate base address.
        label: Parameter name used in the type error.

    Returns:
        The same address when it is an :class:`HttpBaseUrl`.

    Raises:
        TypeError: If ``url`` is not an :class:`HttpBaseUrl`.
    """
    candidate = cast(object, url)
    if not isinstance(candidate, HttpBaseUrl):
        raise TypeError(f"{label} must be an HttpBaseUrl.")
    return candidate


def _require_headers(
    headers: tuple[HttpHeaderField, ...],
) -> tuple[HttpHeaderField, ...]:
    """Return redirect headers after checking the tuple element type.

    Args:
        headers: Candidate header sequence.

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


def _origin(url: HttpBaseUrl) -> tuple[str, str]:
    """Return the scheme and host that define one HTTP origin.

    Args:
        url: Absolute base address.

    Returns:
        Lowercase scheme and host. A default port is omitted.
    """
    return (url.scheme, _host_without_default_port(url.scheme, url.host.casefold()))


def _host_without_default_port(scheme: str, host: str) -> str:
    """Drop an explicit default port so it does not look like a new origin.

    Args:
        scheme: Lowercase ``http`` or ``https`` scheme.
        host: Lowercase host, possibly with a port and IPv6 brackets.

    Returns:
        The host without ``:80`` for HTTP or ``:443`` for HTTPS.
    """
    name, port = _split_host_port(host)
    if port is None:
        return host
    if scheme == _HTTP_SCHEME and port == _HTTP_DEFAULT_PORT:
        return name
    if scheme == _HTTPS_SCHEME and port == _HTTPS_DEFAULT_PORT:
        return name
    return host


def _split_host_port(host: str) -> tuple[str, str | None]:
    """Split a host token into a name and an optional numeric port.

    Args:
        host: Lowercase host token.

    Returns:
        The name, including IPv6 brackets, and the port text. A host without
        a numeric port returns ``None`` for the port.
    """
    if host.startswith("["):
        bracket = host.find("]")
        if bracket < 0 or bracket + 1 >= len(host) or host[bracket + 1] != ":":
            return host, None
        name = host[: bracket + 1]
        port = host[bracket + 2 :]
    else:
        name, separator, port = host.rpartition(":")
        if separator == "":
            return host, None
    if port.isdigit():
        return name, port
    return host, None


def _is_sensitive_header(name: str) -> bool:
    """Return whether a header name carries authorization or a signature.

    Args:
        name: Header field name in its original spelling.

    Returns:
        Whether the field must be removed on a cross-origin redirect.
    """
    folded = name.casefold()
    return folded in _SENSITIVE_HEADER_NAMES or folded.endswith(_SIGNATURE_SUFFIX)
