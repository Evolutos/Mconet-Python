"""Thread-safe manually controlled cancellation signal for tests."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import cast


class ControllableCancellationSignal:
    """Expose read-only cancellation state with an explicit test control.

    The signal structurally implements ``CancellationSignal`` without SDK
    inheritance. :meth:`cancel` applies one atomic first-writer-wins transition,
    preserves its optional reason, and notifies every pending callback once in
    registration order. Later cancellation requests are no-ops.

    Subscribers added before cancellation receive the transition when it occurs.
    Subscribers added after cancellation are notified synchronously before
    :meth:`subscribe` returns. Every returned remover is idempotent, including
    after notification. State and subscription storage are protected by an
    instance-local lock; callbacks execute outside that lock so they may inspect
    state, unsubscribe, subscribe, or request cancellation reentrantly.

    If a pending callback raises, remaining callbacks are still invoked and the
    first exact failure is re-raised after delivery completes. The signal offers
    no reset, second lifecycle, asynchronous task ownership, deadline policy,
    logging, or process-global state.
    """

    __slots__ = (
        "_callbacks",
        "_is_cancelled",
        "_lock",
        "_next_subscription",
        "_reason",
    )

    def __init__(self) -> None:
        """Create one active signal with no reason or pending subscribers."""
        # Each instance owns independent synchronization and callback storage so
        # cancellation in one interaction cannot affect another interaction.
        self._lock = Lock()
        self._callbacks: dict[int, Callable[[str | None], None]] = {}
        self._next_subscription = 0
        self._is_cancelled = False
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether the first cancellation transition has occurred."""
        # Locking makes state observation coherent with reason publication when
        # a test triggers cancellation from another thread.
        with self._lock:
            return self._is_cancelled

    @property
    def reason(self) -> str | None:
        """Return the stable first reason, or ``None`` when absent or active."""
        # is_cancelled distinguishes active state from reasonless cancellation;
        # both intentionally expose None through this property.
        with self._lock:
            return self._reason

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Register one callback or notify it synchronously after cancellation.

        Args:
            callback: Callable receiving the stable optional cancellation reason.

        Returns:
            An idempotent zero-argument remover for a pending subscription.

        Raises:
            TypeError: If ``callback`` is not callable.
            BaseException: Any failure raised by immediate late notification.
        """
        callback_value = cast(object, callback)
        if not callable(callback_value):
            raise TypeError("callback must be callable.")

        with self._lock:
            if self._is_cancelled:
                # Capture the stable reason while holding the same lock used by
                # cancel, then notify outside it to permit callback reentrancy.
                reason = self._reason
                subscription: int | None = None
            else:
                subscription = self._next_subscription
                self._next_subscription += 1
                self._callbacks[subscription] = callback
                reason = None

        if subscription is None:
            # Protocol semantics require late delivery before subscribe returns;
            # a callback failure propagates directly to the subscribing caller.
            callback(reason)
            return _noop_unsubscribe

        def unsubscribe() -> None:
            """Remove this callback if it is still pending."""
            # Dictionary removal under the instance lock is naturally idempotent.
            # If cancel already moved the callback into its delivery snapshot,
            # the subscription is no longer pending and this becomes a no-op.
            with self._lock:
                self._callbacks.pop(subscription, None)

        return unsubscribe

    def cancel(self, reason: str | None = None) -> None:
        """Apply the first cancellation and notify pending subscribers once.

        Args:
            reason: Optional stable reason retained by the winning transition.

        Raises:
            TypeError: If ``reason`` is neither a string nor ``None``.
            BaseException: The first exact callback failure after all callbacks
                in the delivery snapshot have been attempted.
        """
        reason_value = cast(object, reason)
        if reason_value is not None and not isinstance(reason_value, str):
            raise TypeError("reason must be a string or None.")

        with self._lock:
            if self._is_cancelled:
                # First-writer-wins makes repeated or concurrent cancellation a
                # no-op without replacing reason or issuing duplicate delivery.
                return
            self._is_cancelled = True
            self._reason = reason
            callbacks = tuple(self._callbacks.values())
            self._callbacks.clear()

        # Invoke outside the lock in registration order. Continue after a bad
        # callback so one subscriber cannot prevent another from observing the
        # already committed cancellation transition.
        first_failure: BaseException | None = None
        for callback in callbacks:
            try:
                callback(reason)
            except BaseException as error:
                if first_failure is None:
                    # Preserve the first exception object's identity and allow
                    # remaining subscribers to complete their one delivery.
                    first_failure = error
        if first_failure is not None:
            raise first_failure


def _noop_unsubscribe() -> None:
    """Represent removal for an already delivered late subscription."""
    # No callback was stored, so a shared stateless function is safely idempotent.
    return None
