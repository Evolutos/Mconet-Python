"""Missing, repeated, and illegal response Content-Type tests."""

from collections.abc import Callable

from mconet.core.domain import MediaType, ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import (
    HttpHeaderField,
    extract_http_response_media_type,
)


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


def test_extract_http_response_media_type_parses_one_field() -> None:
    """Verify one Content-Type becomes a structured media type."""
    media_type = extract_http_response_media_type(
        (HttpHeaderField("Content-Type", "Application/JSON; charset=utf-8"),)
    )

    assert media_type == MediaType("application", "json", (("charset", "utf-8"),))


def test_extract_http_response_media_type_returns_none_when_absent() -> None:
    """Verify a missing Content-Type is not replaced with a guessed type."""
    assert extract_http_response_media_type(()) is None
    assert (
        extract_http_response_media_type(
            (HttpHeaderField("Accept", "application/json"),)
        )
        is None
    )


def test_extract_http_response_media_type_rejects_repeats_and_illegal_values() -> None:
    """Verify repeated and unparseable types are not selected or joined."""
    repeated = (
        HttpHeaderField("Content-Type", "application/json"),
        HttpHeaderField("content-type", "application/json"),
    )
    illegal = (HttpHeaderField("Content-Type", "not a type"),)

    for headers in (repeated, illegal):
        error = _assert_raises(
            ModelInteractionError,
            lambda headers=headers: extract_http_response_media_type(headers),
            "Content-Type cannot be used",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.code == "invalid_http_response_media_type"
        assert error.category.id == OpenIdentifier("invalid_request")
        assert error.phase.id == OpenIdentifier("transport")
        assert "application/json" not in error.message
        assert error.cause is None
