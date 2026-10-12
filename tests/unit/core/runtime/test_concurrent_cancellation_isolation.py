"""Cancelling one interaction does not cancel the others."""

from __future__ import annotations

from mconet.testing import ControllableCancellationSignal


def test_cancellation_does_not_cross_interactions() -> None:
    """Verify one hundred signals change only when that signal is cancelled."""
    signals = tuple(ControllableCancellationSignal() for _index in range(100))

    signals[17].cancel("stop-17")

    assert signals[17].is_cancelled is True
    assert signals[17].reason == "stop-17"
    assert [signal.is_cancelled for signal in signals if signal is not signals[17]] == (
        [False] * 99
    )
