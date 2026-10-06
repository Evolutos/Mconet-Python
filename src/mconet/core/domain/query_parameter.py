"""Immutable protocol-neutral query parameter name and value pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class QueryParameter:
    """Preserve one query name and value without URL encoding.

    The value object retains caller text exactly. Percent encoding, space
    representation, URL assembly, and transport-specific syntax validation
    remain responsibilities of the selected transport.
    """

    name: str
    """The exact caller-supplied query parameter name."""

    value: str
    """The exact caller-supplied query parameter value."""

    def __post_init__(self) -> None:
        """Require primitive string storage without encoding either field."""
        name = cast(object, self.name)
        value = cast(object, self.value)
        # Enforce only the domain storage types. Keeping raw text here prevents
        # accidental double encoding when the final transport assembles a URL.
        if not isinstance(name, str):
            raise TypeError("QueryParameter name must be a string.")
        if not isinstance(value, str):
            raise TypeError("QueryParameter value must be a string.")
