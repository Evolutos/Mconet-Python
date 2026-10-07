"""Thread-safe deterministic identity generator for tests."""

from __future__ import annotations

from threading import Lock


class DeterministicIdGenerator:
    """Generate a stable, instance-local ``id-{positive integer}`` sequence.

    Every zero-argument instance starts at ``id-1`` and advances by one for each
    :meth:`next_id` call. An instance-local lock makes sequence reservation
    atomic across threads, while Python integers preserve exact values without a
    fixed-width overflow boundary.

    The generator uses no global state, randomness, clock, process identifier,
    caller-selected prefix, seed, reset, peek, or asynchronous behavior. Equal
    call counts on fresh instances therefore produce the same portable decimal
    identifiers independently of test order and execution environment.
    """

    __slots__ = ("_lock", "_next_sequence")

    def __init__(self) -> None:
        """Create an independent sequence whose first value is ``id-1``."""
        # Lock and counter belong exclusively to this instance so one fixture's
        # allocations cannot consume positions from another fixture's sequence.
        self._lock = Lock()
        self._next_sequence = 1

    def next_id(self) -> str:
        """Return the next stable identifier and atomically reserve its position."""
        with self._lock:
            # Snapshot before incrementing so the first call returns id-1. The
            # critical section is the linearization point for concurrent calls.
            sequence = self._next_sequence
            self._next_sequence += 1

        # Decimal integer formatting is locale-independent and contains only
        # portable ASCII characters; formatting needs no shared mutable state.
        return f"id-{sequence}"
