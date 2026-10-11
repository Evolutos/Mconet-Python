"""Absolute HTTP and HTTPS base-address mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from urllib.parse import SplitResult, urlsplit

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.uri import UriValue, validate_uri

_HTTP_SCHEME = "http"
_HTTPS_SCHEME = "https"
_SUPPORTED_SCHEMES = frozenset({_HTTP_SCHEME, _HTTPS_SCHEME})
_HTTP_DEFAULT_PORT = 80
_HTTPS_DEFAULT_PORT = 443
_QUERY_DELIMITER = "?"
_FRAGMENT_DELIMITER = "#"
_SCHEME_AUTHORITY_SEPARATOR = "://"
_ROOT_PATH = "/"
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_URL_CODE = "invalid_http_url"
_INVALID_HTTP_URL_MESSAGE = "HTTP URL is not an absolute HTTP or HTTPS base address."


@dataclass(frozen=True, slots=True)
class HttpBaseUrl:
    """Absolute HTTP or HTTPS base address accepted by the system transport.

    The fields come from the standard-library URL parser. Query, fragment, and
    user information are not part of this value. An empty parser path is stored
    as ``/``. Dot segments stay in the path because this parser does not remove
    them.
    """

    scheme: str
    """Lowercase ``http`` or ``https`` scheme without a trailing colon."""

    host: str
    """Parser host, including a non-default port and IPv6 brackets."""

    path: str
    """Absolute path from the parser, always beginning with ``/``."""

    href: str
    """Serialized base address formed from scheme, host, and path."""

    def __post_init__(self) -> None:
        """Require a base address that contains only scheme, host, and path."""
        scheme = cast(object, self.scheme)
        host = cast(object, self.host)
        path = cast(object, self.path)
        href = cast(object, self.href)

        # Each field is part of the request target, so a non-string cannot be
        # coerced into the serialized href.
        if not isinstance(scheme, str):
            raise TypeError("HttpBaseUrl scheme must be a string.")
        if not isinstance(host, str):
            raise TypeError("HttpBaseUrl host must be a string.")
        if not isinstance(path, str):
            raise TypeError("HttpBaseUrl path must be a string.")
        if not isinstance(href, str):
            raise TypeError("HttpBaseUrl href must be a string.")

        # The href is derived, not an independent URL. A query, fragment, user
        # information, or different scheme cannot be stored beside the parts.
        if scheme not in _SUPPORTED_SCHEMES:
            raise ValueError("HttpBaseUrl scheme must be http or https.")
        if host == "" or any(
            character in "@/?#" or character.isspace() or ord(character) < 32
            for character in host
        ):
            raise ValueError("HttpBaseUrl host must be one authority token.")
        if (
            not path.startswith(_ROOT_PATH)
            or "?" in path
            or "#" in path
            or any(character.isspace() or ord(character) < 32 for character in path)
        ):
            raise ValueError("HttpBaseUrl path must be an absolute path.")
        if href != f"{scheme}{_SCHEME_AUTHORITY_SEPARATOR}{host}{path}":
            raise ValueError("HttpBaseUrl href must match its scheme, host, and path.")


def map_http_url(url: UriValue) -> HttpBaseUrl:
    """Map one absolute URI reference to an HTTP or HTTPS base address.

    The standard-library parser supplies scheme, host, and path. HTTP remains
    available for an explicit local or test URL and is not upgraded to HTTPS.
    User information, a query, and a fragment fail before a base is returned.
    Percent-encoding in the path is preserved and is not decoded. The function
    does not read headers, a body, or credentials, and it does not open a
    connection.

    Args:
        url: Absolute URI reference to validate.

    Returns:
        Frozen base address whose href contains only scheme, host, and path.

    Raises:
        TypeError: If ``url`` is not a :class:`UriValue`.
        ModelInteractionError: If ``url`` is not an absolute HTTP(S) base
            address. The stable code is ``invalid_http_url``. The rejected text
            is omitted from the error.
    """
    candidate = cast(object, url)
    if not isinstance(candidate, UriValue):
        raise TypeError("url must be a UriValue.")
    # A relative reference has no authority of its own. Reject it before the
    # parser can resolve it against an implicit base.
    if not candidate.is_absolute:
        raise _invalid_http_url_error()

    # Query and fragment stay outside the base address. A later query mapper
    # owns ordered query fields, and a fragment must never be sent.
    if _QUERY_DELIMITER in candidate.value or _FRAGMENT_DELIMITER in candidate.value:
        raise _invalid_http_url_error()

    # Reuse URI grammar so a broken percent escape cannot be copied onto the
    # request target. The grammar error is replaced because its only public
    # result is that this base address is unusable.
    try:
        validate_uri(candidate)
    except ValueError:
        raise _invalid_http_url_error() from None

    parsed = urlsplit(candidate.value)
    host = _mapped_host(parsed)
    path = _ROOT_PATH if parsed.path == "" else parsed.path
    if (
        parsed.scheme not in _SUPPORTED_SCHEMES
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or host is None
        or not path.startswith(_ROOT_PATH)
        or not _authority_matches(candidate.value, host)
    ):
        raise _invalid_http_url_error()

    return HttpBaseUrl(
        scheme=parsed.scheme,
        host=host,
        path=path,
        href=f"{parsed.scheme}{_SCHEME_AUTHORITY_SEPARATOR}{host}{path}",
    )


def _mapped_host(parsed: SplitResult) -> str | None:
    """Return the canonical host, or None when the authority is unusable.

    Args:
        parsed: Standard-library split of an absolute URI reference.

    Returns:
        Lowercase host text with IPv6 brackets and a non-default port, or None
        when the host or port cannot be sent.
    """
    hostname = parsed.hostname
    # Missing, blank, or whitespace hosts are not authorities this transport
    # can place on a request line.
    if (
        not isinstance(hostname, str)
        or hostname == ""
        or any(character.isspace() or ord(character) < 32 for character in hostname)
    ):
        return None

    # urlsplit removes the brackets it requires around IPv6. Put them back so
    # the host field remains a single request-line token.
    host = f"[{hostname}]" if ":" in hostname else hostname
    try:
        port = parsed.port
    except ValueError:
        # The parser includes the bad port text in its own message. Drop that
        # exception so the port cannot reach the public error.
        return None
    if port is None:
        return host
    if (parsed.scheme == _HTTP_SCHEME and port == _HTTP_DEFAULT_PORT) or (
        parsed.scheme == _HTTPS_SCHEME and port == _HTTPS_DEFAULT_PORT
    ):
        return host
    return f"{host}:{port}"


def _authority_matches(value: str, host: str) -> bool:
    """Report whether the original text contains the mapped host authority.

    Args:
        value: Original absolute URI text.
        host: Canonical host already accepted for the base address.

    Returns:
        Whether ``value`` has an ``://`` authority that begins with ``host``.
    """
    lowered = value.lower()
    separator_at = lowered.find(_SCHEME_AUTHORITY_SEPARATOR)
    if separator_at < 0:
        return False
    authority = lowered[separator_at + len(_SCHEME_AUTHORITY_SEPARATOR) :]
    expected = host.lower()
    # The next character must end the host or introduce a port or path. A
    # longer host that merely shares this prefix is a different authority.
    if not authority.startswith(expected):
        return False
    remainder = authority[len(expected) :]
    return remainder == "" or remainder.startswith("/") or remainder.startswith(":")


def _invalid_http_url_error() -> ModelInteractionError:
    """Create the content-safe failure for one unusable base address.

    Returns:
        A transport error that does not include the rejected URL.
    """
    # URL text is omitted because it can carry user information or a query
    # secret that must not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_URL_CODE,
        message=_INVALID_HTTP_URL_MESSAGE,
    )
