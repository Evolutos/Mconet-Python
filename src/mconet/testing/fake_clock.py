"""Deterministic manually advanced clock for time-dependent tests."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import Duration, Timestamp

_NANOSECONDS_PER_SECOND = 1_000_000_000


class FakeClock:
    """Return one explicit timestamp and advance it by exact durations.

    Construction requires the starting ``Timestamp`` so tests never depend on
    wall-clock time, a timezone, process start, or a shared epoch default.
    :meth:`now` returns the current immutable value without mutation.
    :meth:`advance` adds one non-negative ``Duration`` using integer nanosecond
    arithmetic and canonicalizes the result back into ``Timestamp`` fields.

    Zero advancement is an identity-preserving no-op. Negative advancement is
    rejected so this clock remains monotonic and deadline tests cannot silently
    move backwards. Configuration and state are instance-local; the fake does
    not sleep, schedule callbacks, interpret deadlines, read a system clock,
    expose reset/set operations, or provide implicit global time.
    """

    __slots__ = ("_current",)

    def __init__(self, initial: Timestamp) -> None:
        """Validate and retain the exact initial timestamp.

        Args:
            initial: Explicit immutable instant returned before any advancement.

        Raises:
            TypeError: If ``initial`` is not a ``Timestamp``.
        """
        initial_value = cast(object, initial)

        # Fail at fixture construction rather than allowing an invalid dynamic
        # value to surface later in unrelated deadline or timeout assertions.
        if not isinstance(initial_value, Timestamp):
            raise TypeError("initial must be a Timestamp.")
        self._current = initial

    def now(self) -> Timestamp:
        """Return the exact current immutable timestamp without advancing it."""
        # Repeated reads preserve identity as well as value, proving the fake has
        # no hidden tick, resolution loss, system-time sampling, or side effect.
        return self._current

    def advance(self, duration: Duration) -> None:
        """Move forward by an exact non-negative duration.

        Args:
            duration: Exact nanoseconds to add to the current timestamp.

        Raises:
            TypeError: If ``duration`` is not a ``Duration``.
            ValueError: If ``duration`` is negative.
        """
        duration_value = cast(object, duration)
        if not isinstance(duration_value, Duration):
            raise TypeError("duration must be a Duration.")
        if duration.total_nanoseconds < 0:
            raise ValueError("duration must not be negative.")
        if duration.total_nanoseconds == 0:
            # Preserve the current object for a semantic no-op instead of
            # manufacturing an indistinguishable replacement timestamp.
            return

        # Convert the canonical pair to one exact integer, add without float or
        # datetime limits, then use floor divmod to normalize positive and
        # pre-epoch instants into a non-negative fractional nanosecond field.
        current_nanoseconds = (
            self._current.epoch_seconds * _NANOSECONDS_PER_SECOND
            + self._current.nanosecond
        )
        advanced_nanoseconds = current_nanoseconds + duration.total_nanoseconds
        epoch_seconds, nanosecond = divmod(
            advanced_nanoseconds,
            _NANOSECONDS_PER_SECOND,
        )
        self._current = Timestamp(epoch_seconds, nanosecond)
