"""Timezone-independent UTC instants with nanosecond precision."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

_TIMESTAMP_PATTERN = re.compile(
    r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})"
    r"T(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]{1,9}))?"
    r"(?P<offset>Z|[+-][0-9]{2}:[0-9]{2})"
)
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


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


def parse_timestamp(value: str) -> Timestamp:
    """Parse an RFC 3339 timestamp and normalize its instant to UTC.

    The accepted form uses an uppercase ``T`` separator and either ``Z`` or a
    numeric ``+/-HH:MM`` offset. Fractional seconds are optional and may contain
    one through nine digits. The ``-00:00`` offset is rejected because RFC 3339
    uses it to indicate an unknown local offset rather than a known UTC instant.

    Args:
        value: Timestamp text with an explicit known offset.

    Returns:
        A canonical UTC :class:`Timestamp` with nanosecond precision.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If the text, calendar value, offset, or precision is invalid.
    """
    candidate = cast(object, value)
    if not isinstance(candidate, str):
        raise TypeError("Timestamp text must be a string.")

    match = _TIMESTAMP_PATTERN.fullmatch(candidate)
    if match is None:
        raise ValueError("Timestamp must use RFC 3339 date-time syntax.")

    offset = _parse_utc_offset(match.group("offset"))
    try:
        local_time = datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            int(match.group("second")),
            tzinfo=offset,
        )
    except ValueError as error:
        raise ValueError("Timestamp contains an invalid calendar value.") from error

    try:
        utc_time = local_time.astimezone(UTC)
        elapsed = utc_time - _UNIX_EPOCH
    except OverflowError as error:
        raise ValueError("Timestamp is outside the supported UTC range.") from error
    epoch_seconds = elapsed.days * 86_400 + elapsed.seconds
    fraction = match.group("fraction")
    nanosecond = int(fraction.ljust(9, "0")) if fraction is not None else 0
    return Timestamp(epoch_seconds=epoch_seconds, nanosecond=nanosecond)


def _parse_utc_offset(value: str) -> timezone:
    """Return a concrete timezone for a validated RFC 3339 offset token."""
    if value == "Z":
        return UTC
    if value == "-00:00":
        raise ValueError("Timestamp offset -00:00 does not identify a UTC instant.")

    hours = int(value[1:3])
    minutes = int(value[4:6])
    if hours > 23 or minutes > 59:
        raise ValueError("Timestamp offset must be between -23:59 and +23:59.")
    total_minutes = hours * 60 + minutes
    if value[0] == "-":
        total_minutes = -total_minutes
    return timezone(timedelta(minutes=total_minutes))
