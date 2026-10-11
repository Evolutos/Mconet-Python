"""Tests that an expired HTTP deadline is a timeout, not a cancellation."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Duration,
    ModelInteractionError,
    OpenIdentifier,
    Timestamp,
)
from mconet.testing import FakeClock
from mconet.transport.http_system import ensure_http_deadline

_START = Timestamp(1_700_000_000)


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


def test_ensure_http_deadline_allows_a_future_deadline_and_no_deadline() -> None:
    """Verify a future instant and an absent deadline do not fail."""
    clock = FakeClock(_START)

    ensure_http_deadline(None, clock.now)
    ensure_http_deadline(Timestamp(_START.epoch_seconds + 1), clock.now)


def test_ensure_http_deadline_fails_when_the_clock_reaches_it() -> None:
    """Verify the deadline instant itself is already too late."""
    clock = FakeClock(_START)
    deadline = Timestamp(_START.epoch_seconds + 5)

    ensure_http_deadline(deadline, clock.now)
    clock.advance(Duration(5_000_000_000))
    error = _assert_raises(
        ModelInteractionError,
        lambda: ensure_http_deadline(deadline, clock.now),
        "HTTP deadline expired",
    )

    assert isinstance(error, ModelInteractionError)
    assert str(error.category) == "timeout"
    assert str(error.phase) == "transport"
    assert error.code == "deadline_exceeded"
    assert error.category.id == OpenIdentifier("timeout")
    assert "170000000" not in error.message
    assert error.cause is None


def test_ensure_http_deadline_rejects_a_non_timestamp_clock() -> None:
    """Verify the gate does not read a system clock of its own."""
    _assert_raises(
        TypeError,
        lambda: ensure_http_deadline(_START, cast(Callable[[], Timestamp], object())),
        "now must be callable",
    )
