"""Tests that cross-origin redirects drop authorization and signature headers."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import UriValue
from mconet.transport.http_system import (
    HttpBaseUrl,
    HttpHeaderField,
    headers_for_http_redirect,
    map_http_url,
)

_SECRET = "redirect-secret-value"


def _url(value: str) -> HttpBaseUrl:
    """Map one absolute base address."""
    return map_http_url(UriValue(value, True))


def _field(name: str, value: str = "kept") -> HttpHeaderField:
    """Build one sendable header field."""
    return HttpHeaderField(name, value)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_same_origin_redirect_keeps_authorization_and_signature_headers() -> None:
    """Verify a path change inside one origin forwards the original fields."""
    headers = (
        _field("Authorization", _SECRET),
        _field("Signature", _SECRET),
        _field("Accept"),
    )
    current = _url("https://models.example.test/v1")
    target = _url("https://models.example.test:443/v1/models")

    forwarded = headers_for_http_redirect(current, target, headers)

    assert forwarded is headers
    assert forwarded[0].value == _SECRET


def test_cross_origin_redirect_drops_authorization_cookie_and_signature() -> None:
    """Verify a different host keeps only non-sensitive fields, in order."""
    accept = _field("Accept", "application/json")
    content_type = _field("Content-Type", "application/json")
    headers = (
        _field("Authorization", _SECRET),
        accept,
        _field("COOKIE", _SECRET),
        _field("Proxy-Authorization", _SECRET),
        _field("Signature-Input", _SECRET),
        _field("X-Amz-Signature", _SECRET),
        _field("Set-Cookie", _SECRET),
        content_type,
    )

    forwarded = headers_for_http_redirect(
        _url("https://models.example.test/v1"),
        _url("https://other.example.test/v1"),
        headers,
    )

    assert forwarded == (accept, content_type)
    assert all(_SECRET not in field.value for field in forwarded)


def test_scheme_or_port_change_is_a_cross_origin_redirect() -> None:
    """Verify a scheme or non-default port change drops authorization."""
    headers = (_field("Authorization", _SECRET), _field("Accept"))
    current = _url("https://models.example.test/v1")

    for target in (
        _url("http://models.example.test/v1"),
        _url("https://models.example.test:8443/v1"),
    ):
        forwarded = headers_for_http_redirect(current, target, headers)
        assert tuple(field.name for field in forwarded) == ("Accept",)


def test_ipv6_same_origin_redirect_keeps_the_original_header_tuple() -> None:
    """Verify bracketed IPv6 addresses use the same origin rule."""
    headers = (_field("Authorization", _SECRET),)
    current = _url("http://[2001:db8::1]/v1")
    target = _url("http://[2001:db8::1]:80/other")

    assert headers_for_http_redirect(current, target, headers) is headers


def test_http_redirect_headers_reject_invalid_arguments_without_values() -> None:
    """Verify type failures happen before any header value is described."""
    current = _url("https://models.example.test/v1")
    headers = (_field("Authorization", _SECRET),)
    _assert_raises(
        TypeError,
        lambda: headers_for_http_redirect(
            cast(HttpBaseUrl, "https://models.example.test/v1"),
            current,
            headers,
        ),
        "current must be an HttpBaseUrl",
    )
    _assert_raises(
        TypeError,
        lambda: headers_for_http_redirect(
            current,
            current,
            cast(tuple[HttpHeaderField, ...], list(headers)),
        ),
        "headers must be a tuple",
    )
