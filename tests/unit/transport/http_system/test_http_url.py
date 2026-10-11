"""Scheme, host, path, and encoding tests for HTTP base addresses."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier, UriValue
from mconet.transport.http_system import HttpBaseUrl, map_http_url

_SECRET = "base-url-secret-value"


def _absolute(value: str) -> UriValue:
    """Build one absolute URI reference without adding a query."""
    return UriValue(value, True)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_map_http_url_maps_https_scheme_host_and_path() -> None:
    """Verify an absolute HTTPS URL keeps its endpoint and path."""
    mapped = map_http_url(_absolute("https://models.example.test/v1/models"))

    assert mapped == HttpBaseUrl(
        scheme="https",
        host="models.example.test",
        path="/v1/models",
        href="https://models.example.test/v1/models",
    )


def test_map_http_url_keeps_an_explicit_http_scheme() -> None:
    """Verify HTTP is not upgraded when the URL selected it."""
    mapped = map_http_url(_absolute("http://127.0.0.1:8080/v1"))

    assert mapped == HttpBaseUrl(
        scheme="http",
        host="127.0.0.1:8080",
        path="/v1",
        href="http://127.0.0.1:8080/v1",
    )


def test_map_http_url_keeps_a_non_default_port_and_drops_defaults() -> None:
    """Verify only the scheme's default port is removed from the host."""
    assert map_http_url(_absolute("https://models.example.test:8443/v1")).host == (
        "models.example.test:8443"
    )
    assert map_http_url(_absolute("https://models.example.test:443/v1")) == HttpBaseUrl(
        scheme="https",
        host="models.example.test",
        path="/v1",
        href="https://models.example.test/v1",
    )
    assert map_http_url(_absolute("http://models.example.test:80/v1")).host == (
        "models.example.test"
    )
    assert map_http_url(_absolute("http://models.example.test:443/v1")).host == (
        "models.example.test:443"
    )


def test_map_http_url_maps_an_ipv6_host_with_brackets() -> None:
    """Verify an IPv6 literal keeps the brackets required on a request line."""
    mapped = map_http_url(_absolute("https://[2001:db8::1]:8443/v1"))

    assert mapped == HttpBaseUrl(
        scheme="https",
        host="[2001:db8::1]:8443",
        path="/v1",
        href="https://[2001:db8::1]:8443/v1",
    )


def test_map_http_url_uses_a_root_path_when_the_url_has_none() -> None:
    """Verify a missing path becomes the root request target."""
    mapped = map_http_url(_absolute("https://models.example.test"))

    assert mapped == HttpBaseUrl(
        scheme="https",
        host="models.example.test",
        path="/",
        href="https://models.example.test/",
    )


def test_map_http_url_preserves_encoding_and_parser_dot_segments() -> None:
    """Verify percent-encoding stays encoded and dot segments are not rewritten."""
    encoded = map_http_url(_absolute("https://models.example.test/v1/my%20model/"))
    dotted = map_http_url(_absolute("https://models.example.test/a/../b"))
    encoded_dots = map_http_url(_absolute("https://models.example.test/%2e%2e/a"))

    # The standard-library parser does not decode escapes or remove dot
    # segments, so both forms remain distinct request targets.
    assert encoded.path == "/v1/my%20model/"
    assert encoded.href == "https://models.example.test/v1/my%20model/"
    assert " " not in encoded.href
    assert dotted.path == "/a/../b"
    assert encoded_dots.path == "/%2e%2e/a"


def test_map_http_url_normalizes_scheme_and_host_case_only() -> None:
    """Verify scheme and host case change while the path spelling stays."""
    mapped = map_http_url(_absolute("HTTP://Models.Example.TEST:8080/V1"))

    assert mapped == HttpBaseUrl(
        scheme="http",
        host="models.example.test:8080",
        path="/V1",
        href="http://models.example.test:8080/V1",
    )


def test_map_http_url_returns_a_frozen_base_address() -> None:
    """Verify callers cannot replace a mapped field."""
    mapped = map_http_url(_absolute("https://models.example.test/v1"))

    assert isinstance(mapped, HttpBaseUrl)
    _assert_raises(
        AttributeError,
        lambda: setattr(mapped, "path", "/other"),
        "cannot assign",
    )


def test_map_http_url_rejects_relative_other_schemes_and_query_forms() -> None:
    """Verify the base mapper accepts only an absolute HTTP(S) address."""
    rejected = (
        UriValue("/v1/models", False),
        UriValue("v1/models", False),
        _absolute("javascript:alert(1)"),
        _absolute("file:///tmp/a"),
        _absolute("ws://models.example.test/v1"),
        _absolute("https:///v1"),
        _absolute("https://models.example.test/v1?q=1"),
        _absolute("https://models.example.test/v1#fragment"),
        _absolute("https://models.example.test/v1?"),
        _absolute("https://models.example.test/v1#"),
        _absolute("https://example.com/%zz"),
        _absolute("https://example.com:abc/v1"),
    )

    for url in rejected:
        error = _assert_raises(
            ModelInteractionError,
            lambda url=url: map_http_url(url),
            "HTTP URL is not an absolute",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.category.id == OpenIdentifier("invalid_request")
        assert error.phase.id == OpenIdentifier("transport")
        assert error.code == "invalid_http_url"
        assert error.cause is None


def test_map_http_url_omits_user_information_and_query_secrets() -> None:
    """Verify rejected URL secrets cannot be recovered from the error."""
    urls = (
        _absolute(f"https://user:{_SECRET}@models.example.test/v1"),
        _absolute(f"https://models.example.test/v1?token={_SECRET}"),
    )

    for url in urls:
        error = _assert_raises(
            ModelInteractionError,
            lambda url=url: map_http_url(url),
            "HTTP URL is not an absolute",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.message == (
            "HTTP URL is not an absolute HTTP or HTTPS base address."
        )
        assert _SECRET not in error.message
        assert _SECRET not in str(error)
        assert all(_SECRET not in str(arg) for arg in error.args)
        assert error.cause is None


def test_http_base_url_rejects_a_mismatched_or_unsafe_value() -> None:
    """Verify a base address cannot carry another scheme or a query."""
    _assert_raises(
        ValueError,
        lambda: HttpBaseUrl(
            "file",
            "models.example.test",
            "/v1",
            "file://models.example.test/v1",
        ),
        "scheme must be http or https",
    )
    _assert_raises(
        ValueError,
        lambda: HttpBaseUrl(
            "https",
            "user@models.example.test",
            "/v1",
            "https://user@models.example.test/v1",
        ),
        "host must be one authority",
    )
    _assert_raises(
        ValueError,
        lambda: HttpBaseUrl(
            "https",
            "models.example.test",
            "/v1",
            "https://models.example.test/v1?token=hidden",
        ),
        "href must match",
    )


def test_map_http_url_rejects_non_uri_values() -> None:
    """Verify arbitrary values are not parsed as URL text."""
    _assert_raises(
        TypeError,
        lambda: map_http_url(cast(UriValue, "https://models.example.test/v1")),
        "url must be a UriValue",
    )
