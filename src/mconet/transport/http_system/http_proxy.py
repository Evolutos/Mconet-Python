"""Proxy source, override, and credential rules for system HTTP."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import SplitResult, urlsplit

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.transport.http_system.http_url import HttpBaseUrl

_HTTP_SCHEME = "http"
_HTTPS_SCHEME = "https"
_SUPPORTED_SCHEMES = frozenset({_HTTP_SCHEME, _HTTPS_SCHEME})
_HTTP_DEFAULT_PORT = 80
_HTTPS_DEFAULT_PORT = 443
_ROOT_PATH = "/"
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_PROXY_CODE = "invalid_http_proxy"
_INVALID_HTTP_PROXY_MESSAGE = "HTTP proxy URL is not an absolute HTTP or HTTPS proxy."
_OVERRIDE_SOURCE = "override"
_ENVIRONMENT_SOURCE = "environment"
HttpProxySource = Literal["override", "environment"]


@dataclass(frozen=True, slots=True, repr=False)
class HttpProxyEndpoint:
    """One HTTP proxy, with credentials kept off the origin request.

    ``username`` and ``password`` authenticate to the proxy. They are not
    request headers and they are omitted from ``repr``.
    """

    scheme: str
    """Lowercase ``http`` or ``https`` scheme of the proxy itself."""

    host: str
    """Proxy host, including a non-default port and IPv6 brackets."""

    username: str | None = None
    """Proxy username, or ``None`` when the proxy URL has no user information."""

    password: str | None = None
    """Proxy password, or ``None`` when the proxy URL has no password."""

    def __post_init__(self) -> None:
        """Require a sendable proxy authority and string credentials."""
        scheme = cast(object, self.scheme)
        host = cast(object, self.host)
        username = cast(object, self.username)
        password = cast(object, self.password)
        if not isinstance(scheme, str):
            raise TypeError("HttpProxyEndpoint scheme must be a string.")
        if not isinstance(host, str):
            raise TypeError("HttpProxyEndpoint host must be a string.")
        if username is not None and not isinstance(username, str):
            raise TypeError("HttpProxyEndpoint username must be a string or None.")
        if password is not None and not isinstance(password, str):
            raise TypeError("HttpProxyEndpoint password must be a string or None.")
        if scheme not in _SUPPORTED_SCHEMES:
            raise ValueError("HttpProxyEndpoint scheme must be http or https.")
        if host == "" or any(
            character in "@/?#" or character.isspace() or ord(character) < 32
            for character in host
        ):
            raise ValueError("HttpProxyEndpoint host must be one authority token.")

    def __repr__(self) -> str:
        """Return a description that omits proxy credentials."""
        # User information can be a password. The host and scheme identify the
        # proxy without repeating that secret.
        return f"HttpProxyEndpoint(scheme={self.scheme!r}, host={self.host!r})"


@dataclass(frozen=True, slots=True)
class HttpProxyOverride:
    """Explicit proxy choice that replaces the process environment.

    ``endpoint`` is ``None`` when the caller forces a direct connection.
    Environment proxy variables are not consulted for this choice.
    """

    endpoint: HttpProxyEndpoint | None
    """Selected proxy, or ``None`` for a direct connection."""

    def __post_init__(self) -> None:
        """Require the endpoint to be a proxy value or an explicit direct choice."""
        endpoint = cast(object, self.endpoint)
        if endpoint is not None and not isinstance(endpoint, HttpProxyEndpoint):
            raise TypeError(
                "HttpProxyOverride endpoint must be an HttpProxyEndpoint or None."
            )


@dataclass(frozen=True, slots=True)
class HttpProxySelection:
    """Proxy chosen for one target, including which source made the choice."""

    source: HttpProxySource
    """``override`` when the caller supplied a choice, otherwise ``environment``."""

    endpoint: HttpProxyEndpoint | None
    """Proxy to use, or ``None`` for a direct connection."""

    def __post_init__(self) -> None:
        """Require a known source and a validated endpoint."""
        source = cast(object, self.source)
        endpoint = cast(object, self.endpoint)
        if source not in (_OVERRIDE_SOURCE, _ENVIRONMENT_SOURCE):
            raise ValueError(
                "HttpProxySelection source must be override or environment."
            )
        if endpoint is not None and not isinstance(endpoint, HttpProxyEndpoint):
            raise TypeError(
                "HttpProxySelection endpoint must be an HttpProxyEndpoint or None."
            )


def map_http_proxy_endpoint(url: str) -> HttpProxyEndpoint:
    """Map one absolute proxy URL to a proxy endpoint.

    HTTP and HTTPS proxy URLs are accepted. User information is stored on the
    endpoint and is not copied into an error or into ``repr``. A path other
    than ``/``, a query, and a fragment are rejected. The function does not
    open a connection or read the process environment.

    Args:
        url: Absolute proxy URL.

    Returns:
        Frozen proxy endpoint.

    Raises:
        TypeError: If ``url`` is not a string.
        ModelInteractionError: If ``url`` is not an absolute HTTP(S) proxy.
            The stable code is ``invalid_http_proxy``. The URL text is omitted.
    """
    candidate = cast(object, url)
    if not isinstance(candidate, str):
        raise TypeError("url must be a string.")
    parsed = urlsplit(candidate)
    host = _mapped_host(parsed)
    if (
        parsed.scheme not in _SUPPORTED_SCHEMES
        or host is None
        or parsed.path not in ("", _ROOT_PATH)
        or parsed.query
        or parsed.fragment
    ):
        raise _invalid_http_proxy_error()
    return HttpProxyEndpoint(
        scheme=parsed.scheme,
        host=host,
        username=parsed.username,
        password=parsed.password,
    )


def select_http_proxy(
    target: HttpBaseUrl,
    environment: Mapping[str, str],
    override: HttpProxyOverride | None = None,
) -> HttpProxySelection:
    """Choose the proxy for one target without mixing two credential sources.

    An override replaces the environment entirely, including a direct
    connection. Otherwise the environment is read from the supplied mapping,
    not from the process environment. ``https_proxy`` is used for an HTTPS
    target and ``http_proxy`` for an HTTP target; ``all_proxy`` is the
    fallback. A matching ``no_proxy`` entry selects a direct connection and
    does not parse the unused proxy URL. Proxy credentials stay on the
    endpoint.

    Args:
        target: Absolute address of the origin request.
        environment: Proxy variables. Lowercase names win over uppercase
            aliases. This mapping is not ``os.environ`` unless the caller
            passes that mapping.
        override: Explicit choice, or ``None`` to use ``environment``.

    Returns:
        The selected source and endpoint. ``endpoint`` is ``None`` for a
        direct connection.

    Raises:
        TypeError: If ``target``, ``environment``, or ``override`` has an
            invalid shape.
        ModelInteractionError: If a selected proxy URL is unusable. The URL
            text is omitted.
    """
    destination = cast(object, target)
    if not isinstance(destination, HttpBaseUrl):
        raise TypeError("target must be an HttpBaseUrl.")
    variables = _require_environment(environment)
    selected = cast(object, override)
    if selected is not None and not isinstance(selected, HttpProxyOverride):
        raise TypeError("override must be an HttpProxyOverride or None.")
    if isinstance(selected, HttpProxyOverride):
        # The override owns the decision. Environment credentials are not
        # copied onto this result.
        return HttpProxySelection(source=_OVERRIDE_SOURCE, endpoint=selected.endpoint)

    if _proxy_bypassed(destination.host, _lookup(variables, "no_proxy")):
        return HttpProxySelection(source=_ENVIRONMENT_SOURCE, endpoint=None)

    configured = _lookup(variables, f"{destination.scheme}_proxy")
    if configured is None:
        configured = _lookup(variables, "all_proxy")
    if configured is None:
        return HttpProxySelection(source=_ENVIRONMENT_SOURCE, endpoint=None)
    return HttpProxySelection(
        source=_ENVIRONMENT_SOURCE,
        endpoint=map_http_proxy_endpoint(configured),
    )


def _require_environment(environment: Mapping[str, str]) -> Mapping[str, str]:
    """Return the proxy mapping after checking keys and values.

    Args:
        environment: Candidate proxy variables.

    Returns:
        The same mapping when every key and value is a string.

    Raises:
        TypeError: If the mapping shape is unusable.
    """
    candidate = cast(object, environment)
    if not isinstance(candidate, Mapping):
        raise TypeError("environment must be a mapping.")
    items = cast(Iterable[object], candidate.items())
    for item in items:
        if not isinstance(item, tuple):
            raise TypeError("environment keys and values must be strings.")
        pair = cast(tuple[object, ...], item)
        if len(pair) != 2:
            raise TypeError("environment keys and values must be strings.")
        key = pair[0]
        value = pair[1]
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("environment keys and values must be strings.")
    return cast(Mapping[str, str], candidate)


def _lookup(environment: Mapping[str, str], name: str) -> str | None:
    """Return one proxy variable, preferring the lowercase name.

    Args:
        environment: Checked proxy variables.
        name: Lowercase variable name.

    Returns:
        The stripped value, or ``None`` when it is absent or blank. The
        uppercase alias is used only when the lowercase name is absent.
    """
    if name in environment:
        value = environment[name]
    elif name.upper() in environment:
        value = environment[name.upper()]
    else:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    return stripped


def _proxy_bypassed(host: str, no_proxy: str | None) -> bool:
    """Return whether ``no_proxy`` selects a direct connection for ``host``.

    Args:
        host: Canonical target host, possibly with a non-default port.
        no_proxy: Comma-separated bypass list, or ``None``.

    Returns:
        Whether the target matches an entry. ``*`` matches every target.
    """
    if no_proxy is None:
        return False
    hostname, port = _split_host_port(host.casefold())
    for raw_entry in no_proxy.split(","):
        entry = raw_entry.strip().casefold()
        if entry == "":
            continue
        if entry == "*":
            return True
        entry_host, entry_port = _split_host_port(entry.lstrip("."))
        if entry_host == "":
            continue
        if entry_port is not None and entry_port != port:
            continue
        if hostname == entry_host or hostname.endswith("." + entry_host):
            return True
    return False


def _split_host_port(host: str) -> tuple[str, str | None]:
    """Split a host token into a name and an optional port.

    Args:
        host: Host token, already case-folded.

    Returns:
        The name, including IPv6 brackets, and the port text when it is numeric.
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


def _mapped_host(parsed: SplitResult) -> str | None:
    """Return the canonical proxy host, or None when it cannot be sent.

    Args:
        parsed: Standard-library split of a proxy URL.

    Returns:
        Lowercase host text with IPv6 brackets and a non-default port, or None.
    """
    hostname = parsed.hostname
    if (
        not isinstance(hostname, str)
        or hostname == ""
        or any(character.isspace() or ord(character) < 32 for character in hostname)
    ):
        return None
    host = f"[{hostname}]" if ":" in hostname else hostname
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        return host
    if (parsed.scheme == _HTTP_SCHEME and port == _HTTP_DEFAULT_PORT) or (
        parsed.scheme == _HTTPS_SCHEME and port == _HTTPS_DEFAULT_PORT
    ):
        return host
    return f"{host}:{port}"


def _invalid_http_proxy_error() -> ModelInteractionError:
    """Create the content-safe failure for one unusable proxy URL.

    Returns:
        A transport error that does not include the rejected URL.
    """
    # Proxy URL text is omitted because it can carry a proxy password.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_PROXY_CODE,
        message=_INVALID_HTTP_PROXY_MESSAGE,
    )
