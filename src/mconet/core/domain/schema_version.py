"""Canonical and forward-compatible schema version values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import cast

_SCHEMA_VERSION_PATTERN = re.compile(
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)"
)


@total_ordering
@dataclass(frozen=True, slots=True)
class SchemaVersion:
    """Represent a canonical ``major.minor`` schema version.

    Components use unsigned canonical decimal notation: zero is written as
    ``0`` and non-zero components cannot have leading zeroes. Comparison is
    numeric by major and then minor component. Component size is deliberately
    unbounded so an older SDK can retain and compare unknown future versions.
    """

    value: str
    """The canonical ``major.minor`` version text."""

    def __post_init__(self) -> None:
        """Require canonical ASCII version text without normalizing input."""
        value = cast(object, self.value)
        # Reject non-canonical input rather than rewriting it, preserving a
        # single stable textual representation for equality and serialization.
        if not isinstance(value, str):
            raise TypeError("SchemaVersion value must be a string.")
        if _SCHEMA_VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError(
                "SchemaVersion must use canonical unsigned major.minor format."
            )

    def __str__(self) -> str:
        """Return the canonical version text."""
        return self.value

    def __lt__(self, other: object) -> bool:
        """Compare schema versions numerically without bounded integers."""
        # Returning NotImplemented lets Python negotiate mixed-type comparison
        # instead of inventing an ordering across unrelated domain values.
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self._comparison_key() < other._comparison_key()

    def _comparison_key(self) -> tuple[int, str, int, str]:
        """Build a magnitude-preserving key from canonical decimal components."""
        major, minor = self.value.split(".")
        # Canonical decimal components have no leading zeroes, so digit count
        # followed by lexical value equals unbounded numeric comparison.
        return len(major), major, len(minor), minor
