"""Tests for Accept and User-Agent defaults that fill only missing names."""

from collections.abc import Callable
from typing import cast

from mconet.transport.http_system import HttpHeaderField, apply_default_http_headers

_FORBIDDEN_DEFAULT_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "content-type",
        "content-length",
        "accept-encoding",
    }
)


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


def test_apply_default_http_headers_appends_only_missing_safe_defaults() -> None:
    """Verify an empty field list gains Accept and User-Agent, in that order."""
    headers = apply_default_http_headers(())

    assert headers == (
        HttpHeaderField("Accept", "application/json"),
        HttpHeaderField("User-Agent", "mconet-sdk"),
    )
    assert {field.name.casefold() for field in headers}.isdisjoint(
        _FORBIDDEN_DEFAULT_NAMES
    )


def test_apply_default_http_headers_keeps_an_existing_field_of_either_case() -> None:
    """Verify a caller value is not replaced or duplicated."""
    supplied = (
        HttpHeaderField("accept", "text/plain"),
        HttpHeaderField("X-Trace", "one"),
    )

    headers = apply_default_http_headers(supplied)

    assert headers == (
        HttpHeaderField("accept", "text/plain"),
        HttpHeaderField("X-Trace", "one"),
        HttpHeaderField("User-Agent", "mconet-sdk"),
    )
    assert headers[0] is supplied[0]
    assert sum(field.name.casefold() == "accept" for field in headers) == 1


def test_apply_default_http_headers_returns_the_same_tuple_when_complete() -> None:
    """Verify an empty caller value still counts as present."""
    supplied = (
        HttpHeaderField("User-Agent", ""),
        HttpHeaderField("ACCEPT", "application/xml"),
    )

    assert apply_default_http_headers(supplied) is supplied


def test_apply_default_http_headers_rejects_a_non_tuple() -> None:
    """Verify a list is not accepted as an already mapped header sequence."""
    _assert_raises(
        TypeError,
        lambda: apply_default_http_headers(
            cast(tuple[HttpHeaderField, ...], [HttpHeaderField("Accept", "*/*")])
        ),
        "headers must be a tuple",
    )
