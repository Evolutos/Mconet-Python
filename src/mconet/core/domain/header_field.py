"""Immutable protocol-neutral header name and value pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class HeaderField:
    """Preserve one header name and value without transport interpretation.

    The value object retains caller text exactly. Header syntax, case-insensitive
    comparison, repeated-field handling, and wire encoding belong to later
    validation, collection, and transport layers.
    """

    name: str
    """The exact caller-supplied header name."""

    value: str
    """The exact caller-supplied header value."""

    def __post_init__(self) -> None:
        """Require primitive string storage without applying HTTP rules."""
        name = cast(object, self.name)
        value = cast(object, self.value)
        # Enforce only the language-level field contract. In particular, this
        # layer does not trim values, fold name case, or validate HTTP syntax.
        if not isinstance(name, str):
            raise TypeError("HeaderField name must be a string.")
        if not isinstance(value, str):
            raise TypeError("HeaderField value must be a string.")
