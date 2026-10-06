"""Immutable absolute and relative URI references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class UriValue:
    """Preserve URI reference text and its declared reference form.

    The value object does not normalize case, escapes, path segments, or query
    ordering. URI syntax and consistency between the text and ``is_absolute``
    are owned by the dedicated validator.
    """

    value: str
    """The exact URI reference text supplied by the producer."""

    is_absolute: bool
    """Whether the value is declared to contain an absolute URI scheme."""

    def __post_init__(self) -> None:
        """Require exact primitive storage without parsing or normalization."""
        value = cast(object, self.value)
        absolute = cast(object, self.is_absolute)
        if not isinstance(value, str):
            raise TypeError("UriValue value must be a string.")
        if type(absolute) is not bool:
            raise TypeError("UriValue is_absolute must be a boolean.")

    def __str__(self) -> str:
        """Return the preserved URI reference text."""
        return self.value
