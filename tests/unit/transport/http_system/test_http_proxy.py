"""Tests for HTTP proxy source, override, and credential boundaries."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier, UriValue
from mconet.transport.http_system import (
    HttpBaseUrl,
    HttpProxyEndpoint,
    HttpProxyOverride,
    map_http_proxy_endpoint,
    map_http_url,
    select_http_proxy,
)

_SECRET = "proxy-secret-value"
_PROXY = f"http://user:{_SECRET}@proxy.example.test:8080"


def _target(value: str) -> HttpBaseUrl:
    """Map one absolute origin address."""
    return map_http_url(UriValue(value, True))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_map_http_proxy_endpoint_keeps_credentials_out_of_repr() -> None:
    """Verify proxy user information is stored on the endpoint and not printed."""
    endpoint = map_http_proxy_endpoint(_PROXY)

    assert endpoint == HttpProxyEndpoint(
        scheme="http",
        host="proxy.example.test:8080",
        username="user",
        password=_SECRET,
    )
    assert _SECRET not in repr(endpoint)
    assert "user" not in repr(endpoint)


def test_map_http_proxy_endpoint_omits_the_url_from_an_invalid_proxy_error() -> None:
    """Verify a rejected proxy URL does not echo its user information."""
    error = _assert_raises(
        ModelInteractionError,
        lambda: map_http_proxy_endpoint(
            f"http://user:{_SECRET}@proxy.example.test/extra"
        ),
        "not an absolute HTTP or HTTPS proxy",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.code == "invalid_http_proxy"
    assert interaction_error.category.id == OpenIdentifier("invalid_request")
    assert interaction_error.phase.id == OpenIdentifier("transport")
    assert _SECRET not in str(interaction_error)
    assert interaction_error.cause is None


def test_select_http_proxy_uses_the_scheme_variable_then_all_proxy() -> None:
    """Verify HTTPS does not inherit an HTTP proxy, and all_proxy is the fallback."""
    target = _target("https://models.example.test/v1")
    selected = select_http_proxy(
        target,
        {"http_proxy": "http://http-proxy.example.test:8080", "https_proxy": _PROXY},
    )

    assert selected.source == "environment"
    assert selected.endpoint is not None
    assert selected.endpoint.host == "proxy.example.test:8080"
    assert selected.endpoint.password == _SECRET
    assert _SECRET not in repr(selected)

    fallback = select_http_proxy(
        target,
        {"all_proxy": "http://all-proxy.example.test:8080"},
    )
    assert fallback.endpoint is not None
    assert fallback.endpoint.host == "all-proxy.example.test:8080"
    assert select_http_proxy(target, {}).endpoint is None


def test_select_http_proxy_lets_an_override_replace_environment_credentials() -> None:
    """Verify an override does not keep the environment proxy password."""
    environment = {"https_proxy": _PROXY}
    override = HttpProxyOverride(
        map_http_proxy_endpoint("http://override.example.test:8080")
    )

    selected = select_http_proxy(
        _target("https://models.example.test/v1"),
        environment,
        override,
    )

    assert selected.source == "override"
    assert selected.endpoint is not None
    assert selected.endpoint.host == "override.example.test:8080"
    assert selected.endpoint.password is None
    assert _SECRET not in repr(selected)


def test_select_http_proxy_accepts_an_explicit_direct_connection() -> None:
    """Verify a direct override ignores a configured environment proxy."""
    selected = select_http_proxy(
        _target("https://models.example.test/v1"),
        {"https_proxy": _PROXY},
        HttpProxyOverride(None),
    )

    assert selected.source == "override"
    assert selected.endpoint is None
    assert _SECRET not in repr(selected)


def test_select_http_proxy_bypasses_a_matching_no_proxy_entry() -> None:
    """Verify no_proxy selects a direct connection before parsing the proxy URL."""
    target = _target("https://models.example.test/v1")
    selected = select_http_proxy(
        target,
        {
            "https_proxy": f"http://user:{_SECRET}@",
            "no_proxy": "other.example.test, .example.test",
        },
    )

    assert selected.source == "environment"
    assert selected.endpoint is None

    starred = select_http_proxy(target, {"https_proxy": _PROXY, "NO_PROXY": "*"})
    assert starred.endpoint is None

    # A port on the bypass entry matches only that port. The default HTTPS
    # port is a different destination, so the proxy remains selected.
    port_specific = select_http_proxy(
        target,
        {"https_proxy": _PROXY, "no_proxy": "models.example.test:8443"},
    )
    assert port_specific.endpoint is not None
    assert port_specific.endpoint.password == _SECRET


def test_select_http_proxy_prefers_the_lowercase_environment_name() -> None:
    """Verify the lowercase variable wins when both cases are present."""
    selected = select_http_proxy(
        _target("http://models.example.test/v1"),
        {
            "http_proxy": "http://lower.example.test:8080",
            "HTTP_PROXY": f"http://user:{_SECRET}@upper.example.test:8080",
        },
    )

    assert selected.endpoint is not None
    assert selected.endpoint.host == "lower.example.test:8080"
    assert selected.endpoint.password is None
    assert _SECRET not in repr(selected)
