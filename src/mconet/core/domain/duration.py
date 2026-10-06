"""Exact signed durations represented in nanoseconds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

_MIN_PORTABLE_NANOSECONDS = -(1 << 63)
_MAX_PORTABLE_NANOSECONDS = (1 << 63) - 1
_UNIT_TO_NANOSECONDS = {
    "seconds": 1_000_000_000,
    "milliseconds": 1_000_000,
    "microseconds": 1_000,
    "nanoseconds": 1,
}


@dataclass(frozen=True, order=True, slots=True)
class Duration:
    """Represent an exact signed number of nanoseconds.

    Zero and negative values are valid. Python's exact integer storage keeps
    construction lossless; portable range and unit conversion are explicit
    validation concerns rather than implicit behavior of this value object.
    """

    total_nanoseconds: int
    """The complete signed duration in nanoseconds."""

    def __post_init__(self) -> None:
        """Require an exact integer without accepting boolean coercion."""
        value = cast(object, self.total_nanoseconds)
        # bool is an int subclass, so an exact type check preserves the numeric
        # contract instead of admitting logical values as durations.
        if type(value) is not int:
            raise TypeError("Duration total_nanoseconds must be an integer.")


def validate_duration(
    value: int,
    unit: Literal[
        "seconds", "milliseconds", "microseconds", "nanoseconds"
    ] = "nanoseconds",
) -> Duration:
    """Convert an integer duration quantity into a portable exact value.

    Conversion uses integer multiplication and never rounds. The resulting
    nanosecond count must fit the signed 64-bit range shared by supported
    platforms.

    Args:
        value: Exact whole units to convert.
        unit: Source unit for the integer quantity.

    Returns:
        A validated duration in canonical nanoseconds.

    Raises:
        TypeError: If the value is not an exact integer or unit is not a string.
        ValueError: If the unit is unsupported or conversion exceeds the range.
    """
    quantity = cast(object, value)
    # Reject coercion up front; conversion must remain exact in the source unit.
    if type(quantity) is not int:
        raise TypeError("Duration value must be an integer.")

    unit_value = cast(object, unit)
    if not isinstance(unit_value, str):
        raise TypeError("Duration unit must be a string.")
    factor = _UNIT_TO_NANOSECONDS.get(unit_value)
    if factor is None:
        raise ValueError(f"Unsupported Duration unit: {unit_value!r}.")

    # Integer multiplication preserves sub-second precision. Range checking is
    # performed after conversion because the portable limit is in nanoseconds.
    total_nanoseconds = quantity * factor
    if not (
        _MIN_PORTABLE_NANOSECONDS <= total_nanoseconds <= _MAX_PORTABLE_NANOSECONDS
    ):
        raise ValueError("Duration exceeds the signed 64-bit nanosecond range.")
    return Duration(total_nanoseconds)
