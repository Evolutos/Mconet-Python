"""Pre-cancel and in-flight cancellation tests for the HTTP bridge."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import CancellationSignal
from mconet.testing import ControllableCancellationSignal
from mconet.transport.http_system import HttpCancellationBridge


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


def test_http_cancellation_bridge_preserves_a_pre_cancelled_reason() -> None:
    """Verify a signal cancelled before the bridge exists keeps that reason."""
    reason = "caller-stopped"
    signal = ControllableCancellationSignal()
    signal.cancel(reason)

    bridge = HttpCancellationBridge(signal)

    assert bridge.is_cancelled is True
    assert bridge.reason is reason
    bridge.close()
    assert bridge.reason is reason


def test_http_cancellation_bridge_preserves_an_in_flight_reason() -> None:
    """Verify cancellation after subscription keeps the same reason object."""
    reason = "caller-stopped-later"
    signal = ControllableCancellationSignal()
    bridge = HttpCancellationBridge(signal)

    assert bridge.is_cancelled is False
    assert bridge.reason is None
    signal.cancel(reason)

    assert bridge.is_cancelled is True
    assert bridge.reason is reason
    signal.cancel("replacement")
    assert bridge.reason is reason
    bridge.close()


def test_http_cancellation_bridge_ignores_cancellation_after_close() -> None:
    """Verify closing removes the subscription without inventing a reason."""
    signal = ControllableCancellationSignal()
    bridge = HttpCancellationBridge(signal)
    bridge.close()
    signal.cancel("after-close")

    assert bridge.is_cancelled is False
    assert bridge.reason is None


def test_http_cancellation_bridge_stays_active_without_a_signal() -> None:
    """Verify a missing caller signal does not cancel the attempt."""
    bridge = HttpCancellationBridge(None)

    assert bridge.is_cancelled is False
    assert bridge.reason is None
    bridge.close()


def test_http_cancellation_bridge_rejects_a_non_signal() -> None:
    """Verify an arbitrary object is not treated as caller cancellation."""
    _assert_raises(
        TypeError,
        lambda: HttpCancellationBridge(cast(CancellationSignal, "stop")),
        "signal must implement CancellationSignal",
    )
