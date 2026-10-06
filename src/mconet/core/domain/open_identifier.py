"""Open string identifiers shared by extensible Mconet domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class OpenIdentifier:
    """Preserve an extensible identifier as an immutable, case-sensitive value.

    This value object deliberately does not restrict namespaces, length,
    whitespace, casing, or known values. Semantic validation belongs to the
    separate OpenIdentifier validator so future identifiers remain lossless.
    """

    value: str
    """The exact identifier text supplied by the producer."""

    def __post_init__(self) -> None:
        """Require the primitive string representation without normalizing it."""
        # Type membership is a value-object invariant; format and namespace
        # rules remain outside this type for the dedicated validator work item.
        value = cast(object, self.value)
        if not isinstance(value, str):
            raise TypeError("OpenIdentifier value must be a string.")

    def __str__(self) -> str:
        """Return the preserved identifier text for explicit string contexts."""
        return self.value
