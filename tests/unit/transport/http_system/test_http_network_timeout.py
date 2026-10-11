"""Tests that platform timeouts become one stable timeout code."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.transport.http_system import normalize_http_network_timeout

_HOST = "timeout-secret.example"


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


def test_normalize_http_network_timeout_hides_the_platform_message() -> None:
    """Verify a platform timeout drops host text from its message."""
    for error in (TimeoutError(f"timed out connecting to {_HOST}"), TimeoutError()):
        normalized = normalize_http_network_timeout(error)

        assert isinstance(normalized, ModelInteractionError)
        assert str(normalized.category) == "timeout"
        assert str(normalized.phase) == "transport"
        assert normalized.code == "network_timeout"
        assert normalized.category.id == OpenIdentifier("timeout")
        assert normalized.code != "deadline_exceeded"
        assert _HOST not in str(normalized)
        assert normalized.cause is None


def test_normalize_http_network_timeout_rejects_other_failures() -> None:
    """Verify cancellation and connection failures stay out of this mapping."""
    _assert_raises(
        TypeError,
        lambda: normalize_http_network_timeout(
            cast(BaseException, ConnectionError("down"))
        ),
        "error must be a TimeoutError",
    )
