"""Whitelist tests for system HTTP method mapping."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import map_http_method

_SUPPORTED_HTTP_METHODS = (
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)
_REJECTED_METHOD_TEXT = "GET\r\nX-Credential: method-secret-value"


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # The fragment distinguishes a method-policy failure from a type error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_map_http_method_accepts_each_whitelist_member_unchanged() -> None:
    """Verify one supported token maps to itself and stays idempotent."""
    for method in _SUPPORTED_HTTP_METHODS:
        # The plan's spelling is the request-line token. Mapping must not
        # allocate a replacement or fold case onto another member.
        assert map_http_method(method) is method
        assert map_http_method(map_http_method(method)) is method


def test_map_http_method_rejects_other_spellings_and_tokens() -> None:
    """Verify case, whitespace, and unreviewed methods stay outside the map."""
    rejected = (
        "connect",
        "CONNECT",
        "TRACE",
        "TRACK",
        "QUERY",
        "get",
        "Get",
        "Post",
        "Patch",
        "FOO",
        "",
        " POST",
        "POST ",
        "GET\n",
        "GET\r\nHost: example",
    )

    for method in rejected:
        error = _assert_raises(
            ModelInteractionError,
            lambda method=method: map_http_method(method),
            "HTTP method is not supported",
        )
        assert isinstance(error, ModelInteractionError)
        assert str(error.category.id) == "invalid_request"
        assert isinstance(error.category.id, OpenIdentifier)
        assert str(error.phase.id) == "transport"
        assert error.code == "unsupported_http_method"
        assert error.status_code is None
        assert error.cause is None


def test_map_http_method_omits_rejected_text_from_the_error() -> None:
    """Verify an injected method token cannot be recovered from the error."""
    error = _assert_raises(
        ModelInteractionError,
        lambda: map_http_method(_REJECTED_METHOD_TEXT),
        "HTTP method is not supported",
    )

    # Header-shaped method text must not reach message, arguments, or text form.
    assert isinstance(error, ModelInteractionError)
    assert error.message == "HTTP method is not supported by the system HTTP transport."
    assert "method-secret-value" not in error.message
    assert "method-secret-value" not in str(error)
    assert all("method-secret-value" not in str(arg) for arg in error.args)
    assert error.cause is None


def test_map_http_method_rejects_non_strings() -> None:
    """Verify arbitrary values are not coerced into method tokens."""
    _assert_raises(
        TypeError,
        lambda: map_http_method(cast(str, None)),
        "method must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: map_http_method(cast(str, b"GET")),
        "method must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: map_http_method(cast(str, 1)),
        "method must be a string",
    )
