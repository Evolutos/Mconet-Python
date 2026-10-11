"""Tests that Content-Type comes from the planned media type."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import MediaType, ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import HttpHeaderField, apply_http_content_type

_JSON_BODY = b'{"message":"not used"}'


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


def test_apply_http_content_type_uses_the_planned_type_for_json_bytes() -> None:
    """Verify JSON-looking bytes do not select application/json."""
    headers = apply_http_content_type((), MediaType("text", "plain"))

    assert headers == (HttpHeaderField("Content-Type", "text/plain"),)
    assert _JSON_BODY.startswith(b"{")
    assert "json" not in headers[0].value


def test_apply_http_content_type_keeps_planned_parameters_in_order() -> None:
    """Verify charset and boundary text come from the plan."""
    media_type = MediaType(
        "multipart",
        "form-data",
        (("charset", "utf-8"), ("boundary", "line one")),
    )

    headers = apply_http_content_type((), media_type)

    assert headers == (
        HttpHeaderField(
            "Content-Type",
            'multipart/form-data; charset=utf-8; boundary="line one"',
        ),
    )


def test_apply_http_content_type_keeps_one_equivalent_existing_field() -> None:
    """Verify a matching caller spelling is not rewritten."""
    supplied = (HttpHeaderField("content-type", "Application/JSON"),)

    assert apply_http_content_type(supplied, MediaType("application", "json")) is (
        supplied
    )


def test_apply_http_content_type_rejects_a_different_or_repeated_value() -> None:
    """Verify a conflicting type is not replaced from the payload."""
    conflicts = (
        (
            (HttpHeaderField("Content-Type", "text/plain"),),
            MediaType("application", "json"),
        ),
        (
            (
                HttpHeaderField("Content-Type", "application/json"),
                HttpHeaderField("content-type", "application/json"),
            ),
            MediaType("application", "json"),
        ),
        (
            (HttpHeaderField("Content-Type", "not a type"),),
            MediaType("application", "json"),
        ),
    )

    for headers, media_type in conflicts:
        error = _assert_raises(
            ModelInteractionError,
            lambda headers=headers, media_type=media_type: apply_http_content_type(
                headers, media_type
            ),
            "Content-Type does not match",
        )
        assert isinstance(error, ModelInteractionError)
        assert error.code == "invalid_http_content_type"
        assert error.category.id == OpenIdentifier("invalid_request")
        assert error.phase.id == OpenIdentifier("transport")
        assert error.cause is None


def test_apply_http_content_type_rejects_a_non_media_type() -> None:
    """Verify a body string is not parsed as a planned media type."""
    _assert_raises(
        TypeError,
        lambda: apply_http_content_type((), cast(MediaType, "application/json")),
        "media_type must be a MediaType",
    )
