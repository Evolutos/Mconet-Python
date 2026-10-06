"""Timezone-independent UTC instants with nanosecond precision."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal, cast

_TIMESTAMP_PATTERN = re.compile(
    r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})"
    r"T(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]{1,9}))?"
    r"(?P<offset>Z|[+-][0-9]{2}:[0-9]{2})"
)
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_PRECISION_DIGITS = {
    "seconds": 0,
    "milliseconds": 3,
    "microseconds": 6,
    "nanoseconds": 9,
}


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

    # Full matching prevents trailing data and admits only the explicitly
    # supported RFC 3339 precision and offset forms.
    match = _TIMESTAMP_PATTERN.fullmatch(candidate)
    if match is None:
        raise ValueError("Timestamp must use RFC 3339 date-time syntax.")

    # Parse the declared offset before calendar construction so unknown and
    # out-of-range offsets receive stable domain errors.
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

    # Normalize the instant through UTC and compute seconds with timedelta
    # integer fields, avoiding platform timestamp and float precision limits.
    try:
        utc_time = local_time.astimezone(UTC)
        elapsed = utc_time - _UNIX_EPOCH
    except OverflowError as error:
        raise ValueError("Timestamp is outside the supported UTC range.") from error
    epoch_seconds = elapsed.days * 86_400 + elapsed.seconds
    fraction = match.group("fraction")
    # Right-padding preserves the supplied decimal fraction exactly at the
    # canonical nine-digit nanosecond scale.
    nanosecond = int(fraction.ljust(9, "0")) if fraction is not None else 0
    return Timestamp(epoch_seconds=epoch_seconds, nanosecond=nanosecond)


def serialize_timestamp(
    timestamp: Timestamp,
    precision: Literal[
        "seconds", "milliseconds", "microseconds", "nanoseconds"
    ] = "nanoseconds",
) -> str:
    """Serialize a UTC timestamp without silently discarding precision.

    Output uses a canonical RFC 3339 UTC form with ``Z`` and a fixed number of
    fractional digits selected by ``precision``. A lower precision is accepted
    only when the timestamp is exactly representable at that precision; the
    serializer never rounds or truncates fractional nanoseconds.

    Args:
        timestamp: The canonical UTC instant to serialize.
        precision: The required fractional-second precision.

    Returns:
        Canonical RFC 3339 text at the selected exact precision.

    Raises:
        TypeError: If an argument has the wrong runtime type.
        ValueError: If precision is unsupported, would lose data, or the instant
            is outside the RFC 3339 four-digit year range.
    """
    candidate = cast(object, timestamp)
    # Require the domain value rather than accepting datetime, whose timezone
    # and microsecond limits cannot preserve this contract.
    if not isinstance(candidate, Timestamp):
        raise TypeError("timestamp must be a Timestamp.")

    precision_value = cast(object, precision)
    if not isinstance(precision_value, str):
        raise TypeError("Timestamp precision must be a string.")
    fractional_digits = _PRECISION_DIGITS.get(precision_value)
    if fractional_digits is None:
        raise ValueError(f"Unsupported Timestamp precision: {precision_value!r}.")

    # A coarser representation is valid only when every omitted decimal digit
    # is zero. Rejecting avoids platform-specific rounding or truncation.
    quantum = 10 ** (9 - fractional_digits)
    if candidate.nanosecond % quantum != 0:
        raise ValueError("Timestamp cannot be represented at the requested precision.")

    # datetime is used only for exact calendar decomposition. Integer timedelta
    # arithmetic avoids float timestamps and exposes its supported year range.
    try:
        utc_time = _UNIX_EPOCH + timedelta(seconds=candidate.epoch_seconds)
    except OverflowError as error:
        raise ValueError(
            "Timestamp is outside the RFC 3339 four-digit year range."
        ) from error

    date_time = (
        f"{utc_time.year:04d}-{utc_time.month:02d}-{utc_time.day:02d}"
        f"T{utc_time.hour:02d}:{utc_time.minute:02d}:{utc_time.second:02d}"
    )
    # Fixed-width fractions make the selected precision explicit. Seconds omit
    # the decimal point entirely, while other modes take exact leading digits.
    if fractional_digits == 0:
        return f"{date_time}Z"
    fraction = f"{candidate.nanosecond:09d}"[:fractional_digits]
    return f"{date_time}.{fraction}Z"


def _parse_utc_offset(value: str) -> timezone:
    """Return a concrete timezone for a validated RFC 3339 offset token."""
    # Z is the canonical zero-offset token; -00:00 instead signals an unknown
    # local offset and cannot identify an absolute instant.
    if value == "Z":
        return UTC
    if value == "-00:00":
        raise ValueError("Timestamp offset -00:00 does not identify a UTC instant.")

    hours = int(value[1:3])
    minutes = int(value[4:6])
    if hours > 23 or minutes > 59:
        raise ValueError("Timestamp offset must be between -23:59 and +23:59.")
    total_minutes = hours * 60 + minutes
    # Apply the sign only after magnitude validation so both directions share
    # identical limits.
    if value[0] == "-":
        total_minutes = -total_minutes
    return timezone(timedelta(minutes=total_minutes))
