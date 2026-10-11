"""Repeated-field and case tests for HTTP header mapping."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    HeaderField,
    Headers,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.transport.http_system import HttpHeaderField, map_http_headers

_SECRET = "header-secret-value"


def _headers(*pairs: tuple[str, str]) -> Headers:
    """Build ordered header fields without folding their names."""
    return Headers(tuple(HeaderField(name, value) for name, value in pairs))


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


def test_map_http_headers_preserves_repeats_order_and_name_case() -> None:
    """Verify repeated names stay separate and keep their spelling."""
    headers = _headers(
        ("Accept", "application/json"),
        ("X-Request-Id", "one"),
        ("accept", "application/problem+json"),
        ("x-request-id", "two"),
    )

    mapped = map_http_headers(headers)

    # Case-insensitive lookup must not merge these fields or rewrite names.
    assert mapped == (
        HttpHeaderField("Accept", "application/json"),
        HttpHeaderField("X-Request-Id", "one"),
        HttpHeaderField("accept", "application/problem+json"),
        HttpHeaderField("x-request-id", "two"),
    )
    assert headers.values[0].name == "Accept"
    assert [field.name for field in mapped].count("Accept") == 1


def test_map_http_headers_does_not_add_defaults_or_trim_values() -> None:
    """Verify mapping copies only the supplied fields."""
    mapped = map_http_headers(_headers(("X-Empty", ""), ("X-Space", " value ")))

    assert mapped == (
        HttpHeaderField("X-Empty", ""),
        HttpHeaderField("X-Space", " value "),
    )
    assert all(
        field.name.casefold() not in {"accept", "user-agent"} for field in mapped
    )
    assert map_http_headers(Headers()) == ()


def test_map_http_headers_rejects_controls_without_copying_the_value() -> None:
    """Verify CR, LF, and a non-token name fail closed."""
    rejected = (
        _headers(("X-Ok", f"{_SECRET}\r\nX-Injected: 1")),
        _headers((f"X-{_SECRET}\n", "1")),
        _headers(("Bad Name", "1")),
        _headers(("", "1")),
        _headers(("X-Ok", "line\x7f")),
    )

    for headers in rejected:
        error = _assert_raises(
            ModelInteractionError,
            lambda headers=headers: map_http_headers(headers),
            "HTTP header cannot be sent",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.category.id == OpenIdentifier("invalid_request")
        assert error.phase.id == OpenIdentifier("transport")
        assert error.code == "invalid_http_header"
        assert error.message == "HTTP header cannot be sent."
        assert _SECRET not in error.message
        assert _SECRET not in str(error)
        assert error.cause is None


def test_map_http_headers_rejects_non_header_collections() -> None:
    """Verify arbitrary values are not treated as header fields."""
    _assert_raises(
        TypeError,
        lambda: map_http_headers(cast(Headers, (("Accept", "application/json"),))),
        "headers must be Headers",
    )
