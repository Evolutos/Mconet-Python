"""Exact signed durations represented in nanoseconds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


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
        if type(value) is not int:
            raise TypeError("Duration total_nanoseconds must be an integer.")
