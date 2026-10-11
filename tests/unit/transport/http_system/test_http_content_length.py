"""Missing, matching, and conflicting Content-Length tests."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import HttpHeaderField, apply_http_content_length

_SECRET = "length-secret-value"


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


def test_apply_http_content_length_appends_the_decimal_length_when_missing() -> None:
    """Verify empty and binary bodies gain one exact length."""
    empty = apply_http_content_length((), b"")
    binary = apply_http_content_length(
        (HttpHeaderField("Accept", "application/json"),),
        b"\x00\xff",
    )

    assert empty == (HttpHeaderField("Content-Length", "0"),)
    assert binary == (
        HttpHeaderField("Accept", "application/json"),
        HttpHeaderField("Content-Length", "2"),
    )


def test_apply_http_content_length_keeps_one_exact_existing_field() -> None:
    """Verify a matching value keeps its original name spelling."""
    supplied = (
        HttpHeaderField("content-length", "2"),
        HttpHeaderField("Accept", "application/json"),
    )

    assert apply_http_content_length(supplied, b"ab") is supplied


def test_apply_http_content_length_rejects_a_conflicting_value() -> None:
    """Verify a different, padded, or repeated length is not rewritten."""
    conflicts = (
        ((HttpHeaderField("Content-Length", "1"),), b"ab"),
        ((HttpHeaderField("Content-Length", "00"),), b""),
        ((HttpHeaderField("Content-Length", f"1{_SECRET}"),), b"ab"),
        (
            (
                HttpHeaderField("Content-Length", "2"),
                HttpHeaderField("content-length", "2"),
            ),
            b"ab",
        ),
    )

    for headers, body in conflicts:
        error = _assert_raises(
            ModelInteractionError,
            lambda headers=headers, body=body: apply_http_content_length(headers, body),
            "Content-Length does not match",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.code == "invalid_http_content_length"
        assert error.category.id == OpenIdentifier("invalid_request")
        assert error.phase.id == OpenIdentifier("transport")
        assert _SECRET not in str(error)
        assert error.cause is None


def test_apply_http_content_length_rejects_invalid_inputs() -> None:
    """Verify text is not measured as a body."""
    _assert_raises(
        TypeError,
        lambda: apply_http_content_length((), cast(bytes, "ab")),
        "body must be bytes",
    )
