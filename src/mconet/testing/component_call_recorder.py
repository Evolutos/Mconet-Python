"""Ordered component-call recording for pipeline tests."""

from __future__ import annotations

from threading import Lock
from typing import cast


class ComponentCallRecorder:
    """Record caller-owned component operation labels in invocation order.

    :meth:`record` appends the exact supplied string at one instance-local,
    lock-protected linearization point. Pipeline fixtures can therefore record
    labels such as ``plan``, ``encode``, ``authorize``, ``send``, ``decode``, and
    ``parse`` and compare the resulting complete order deterministically.

    Labels are intentionally open and preserved without trimming, case changes,
    namespace parsing, or a closed stage list so future components and failure
    probes can use the same recorder. Repeated labels remain distinct calls.

    :attr:`calls` returns a fresh immutable tuple snapshot. The recorder stores
    no arguments, results, exceptions, timestamps, component instances, or
    secrets, and offers no reset, assertion, wrapping, or dynamic filtering API.
    Each test owns a fresh instance instead of mutating prior call history.
    """

    __slots__ = ("_calls", "_lock")

    def __init__(self) -> None:
        """Create one independent empty ordered call history."""
        # Synchronization and storage are instance-local so unrelated tests and
        # pipeline executions cannot consume or reorder each other's evidence.
        self._lock = Lock()
        self._calls: list[str] = []

    @property
    def calls(self) -> tuple[str, ...]:
        """Return an immutable snapshot of labels in recorded order."""
        with self._lock:
            # Copy membership while holding the same lock as record. Once built,
            # the tuple remains time-bounded even as later calls are appended.
            return tuple(self._calls)

    def record(self, call: str) -> None:
        """Append one exact component operation label.

        Args:
            call: Caller-owned operation label retained without normalization.

        Raises:
            TypeError: If ``call`` is not a string.
        """
        call_value = cast(object, call)
        if not isinstance(call_value, str):
            raise TypeError("call must be a string.")

        with self._lock:
            # List append under the lock is the observable order point. Duplicate,
            # empty, and extension labels are data and remain byte-for-byte exact.
            self._calls.append(call)
