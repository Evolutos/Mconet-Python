"""Timezone-independent UTC instants with nanosecond precision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, order=True, slots=True)
class Timestamp:
    """Represent a UTC instant relative to the Unix epoch.

    ``epoch_seconds`` is the whole-second floor of the instant relative to
    1970-01-01T00:00:00Z. ``nanosecond`` is the non-negative fractional part
    in the inclusive range 0 through 999,999,999. This canonical pair avoids
    local timezone state and preserves precision beyond ``datetime``'s
    microsecond limit.
    """

    epoch_seconds: int
    """Whole seconds from the Unix epoch, using floor semantics."""

    nanosecond: int = 0
    """The non-negative fractional second at nanosecond precision."""

    def __post_init__(self) -> None:
        """Require canonical integer fields and a normalized fraction."""
        seconds = cast(object, self.epoch_seconds)
        fraction = cast(object, self.nanosecond)
        # Exact type checks reject bool, whose integer subclass behavior would
        # otherwise create surprising serialized timestamps.
        if type(seconds) is not int:
            raise TypeError("Timestamp epoch_seconds must be an integer.")
        if type(fraction) is not int:
            raise TypeError("Timestamp nanosecond must be an integer.")
        if not 0 <= fraction < 1_000_000_000:
            raise ValueError("Timestamp nanosecond must be between 0 and 999999999.")
