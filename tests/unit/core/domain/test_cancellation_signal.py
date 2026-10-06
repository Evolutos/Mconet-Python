"""Structural and lifecycle contract tests for CancellationSignal."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import CancellationSignal


class _ControllableSignal:
    """Small contract fixture whose control operation is not part of the protocol."""

    def __init__(self) -> None:
        """Create an active signal with no subscribers or cancellation reason."""
        # A monotonically increasing key lets each unsubscribe closure remove
        # exactly its own pending callback without comparing callable identity.
        self._next_subscription = 0
        self._callbacks: dict[int, Callable[[str | None], None]] = {}
        self._is_cancelled = False
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether this fixture has accepted its first cancellation."""
        # Reading state has no side effect and does not consume cancellation.
        return self._is_cancelled

    @property
    def reason(self) -> str | None:
        """Return the stable reason retained by the first cancellation."""
        # Active signals and cancellations without a reason both expose None, as
        # distinguished by the separate is_cancelled state property.
        return self._reason

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Register one pending callback or notify a late subscriber immediately."""
        # Pre-cancelled signals notify synchronously so callers cannot miss the
        # transition between checking state and subscribing.
        if self._is_cancelled:
            callback(self._reason)
            return _noop_unsubscribe

        subscription = self._next_subscription
        self._next_subscription += 1
        self._callbacks[subscription] = callback
        is_active = True

        def unsubscribe() -> None:
            """Remove this pending callback at most once."""
            nonlocal is_active
            # Clearing the closure guard first makes repeated calls no-ops even
            # after cancellation has already removed the callback collection.
            if not is_active:
                return
            is_active = False
            self._callbacks.pop(subscription, None)

        return unsubscribe

    def cancel(self, reason: str | None = None) -> None:
        """Apply the first cancellation and notify every pending callback once."""
        # The first transition owns both state and reason. Later requests return
        # before mutating either value or issuing duplicate notifications.
        if self._is_cancelled:
            return
        self._is_cancelled = True
        self._reason = reason

        callbacks = tuple(self._callbacks.values())
        self._callbacks.clear()
        # Clear storage before invoking application callbacks so reentrant
        # unsubscribe or cancellation calls cannot trigger a second delivery.
        for callback in callbacks:
            callback(reason)


def _noop_unsubscribe() -> None:
    """Represent an already-completed subscription removal."""
    # A shared stateless function is safe because late subscribers have no
    # pending callback left to remove.
    return None


def test_cancellation_signal_accepts_structural_implementation() -> None:
    """Verify implementations need no SDK base class or controller surface."""
    signal = _ControllableSignal()

    # Runtime recognition checks only read state and subscription behavior;
    # cancel remains an implementation-owned control operation.
    assert isinstance(signal, CancellationSignal)
    assert not signal.is_cancelled
    assert signal.reason is None


def test_cancellation_signal_rejects_incomplete_surface() -> None:
    """Verify state without subscription behavior cannot satisfy the protocol."""

    class _StateOnlySignal:
        """Intentionally omit subscribe from an otherwise signal-shaped object."""

        is_cancelled = False
        reason: str | None = None

    # Consumers require subscription to observe cancellation after work starts;
    # polling-only objects are therefore not valid signals.
    assert not isinstance(_StateOnlySignal(), CancellationSignal)


def test_cancellation_signal_delivers_execution_time_cancellation_once() -> None:
    """Verify pending subscribers observe the first reason exactly once."""
    signal = _ControllableSignal()
    first_reasons: list[str | None] = []
    second_reasons: list[str | None] = []
    signal.subscribe(first_reasons.append)
    signal.subscribe(second_reasons.append)

    signal.cancel("caller_requested")
    signal.cancel("later_reason")

    # Idempotent cancellation retains the first reason and never invokes a
    # pending subscriber again for later requests.
    assert signal.is_cancelled
    assert signal.reason == "caller_requested"
    assert first_reasons == ["caller_requested"]
    assert second_reasons == ["caller_requested"]


def test_cancellation_signal_delivers_pre_cancellation_to_late_subscriber() -> None:
    """Verify subscribing after cancellation cannot miss the stable transition."""
    signal = _ControllableSignal()
    signal.cancel()
    reasons: list[str | None] = []

    unsubscribe = signal.subscribe(reasons.append)
    unsubscribe()
    unsubscribe()

    # Notification occurs during subscribe and the returned remover is already
    # complete, so repeated cleanup cannot change delivery or signal state.
    assert signal.is_cancelled
    assert signal.reason is None
    assert reasons == [None]


def test_cancellation_signal_unsubscribe_is_idempotent() -> None:
    """Verify repeated removal prevents future notification without side effects."""
    signal = _ControllableSignal()
    reasons: list[str | None] = []
    unsubscribe = signal.subscribe(reasons.append)

    unsubscribe()
    unsubscribe()
    signal.cancel("after_removal")

    # The removed callback stays silent while cancellation state and its reason
    # remain observable to other consumers.
    assert reasons == []
    assert signal.is_cancelled
    assert signal.reason == "after_removal"


def test_cancellation_signal_unsubscribe_after_delivery_is_safe() -> None:
    """Verify cleanup remains idempotent after a callback has already run."""
    signal = _ControllableSignal()
    reasons: list[str | None] = []
    unsubscribe = signal.subscribe(reasons.append)

    signal.cancel("completed")
    unsubscribe()
    unsubscribe()

    # Delivery clears source storage before callbacks run; a retained remover
    # can still be called during interaction cleanup without duplicate effects.
    assert reasons == ["completed"]
