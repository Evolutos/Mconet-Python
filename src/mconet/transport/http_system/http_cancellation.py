"""Bridge from a caller cancellation signal to one HTTP attempt."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import cast

from mconet.core.domain.cancellation_signal import CancellationSignal


class HttpCancellationBridge:
    """Observe one caller signal without replacing its cancellation reason.

    A signal that is already cancelled notifies this bridge before construction
    returns. A signal cancelled later notifies the same callback once. In both
    cases the reason object is the one supplied by the signal. ``None`` means
    the caller did not supply a signal, so this attempt is not cancelled here.
    Closing the bridge removes a pending subscription and does not clear a
    reason that was already delivered.
    """

    __slots__ = ("_cancelled", "_lock", "_reason", "_unsubscribe")

    def __init__(self, signal: CancellationSignal | None) -> None:
        """Subscribe to ``signal`` or record that no caller signal exists.

        Args:
            signal: Read-only caller cancellation signal, or ``None``.

        Raises:
            TypeError: If ``signal`` does not implement
                :class:`CancellationSignal`.
        """
        self._lock = Lock()
        self._cancelled = False
        self._reason: str | None = None
        self._unsubscribe: Callable[[], None] | None = None
        if signal is None:
            return

        candidate = cast(object, signal)
        # Structural recognition accepts application-owned signals. A bare
        # boolean or string cannot be observed as cancellation state.
        if not isinstance(candidate, CancellationSignal):
            raise TypeError("signal must implement CancellationSignal.")

        def observe(reason: str | None) -> None:
            """Store the first delivered reason without copying its text."""
            # Publish the reason before the flag so a reader that observes
            # cancellation also observes the reason that caused it.
            with self._lock:
                self._reason = reason
                self._cancelled = True

        # Late subscription delivers an existing cancellation before this call
        # returns, so a pre-cancelled attempt is visible immediately.
        self._unsubscribe = candidate.subscribe(observe)

    @property
    def is_cancelled(self) -> bool:
        """Return whether the caller signal has cancelled this attempt."""
        with self._lock:
            return self._cancelled

    @property
    def reason(self) -> str | None:
        """Return the preserved caller reason, or ``None`` when absent."""
        with self._lock:
            return self._reason

    def close(self) -> None:
        """Drop a pending subscription without erasing a delivered reason."""
        # Release the lock before unsubscribing. The signal may notify this
        # bridge while removal runs, and that callback also takes the lock.
        with self._lock:
            unsubscribe = self._unsubscribe
            self._unsubscribe = None
        if unsubscribe is not None:
            unsubscribe()
