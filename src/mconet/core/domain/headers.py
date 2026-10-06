"""Immutable ordered collection of protocol-neutral header fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.header_field import HeaderField


@dataclass(frozen=True, slots=True)
class Headers:
    """Preserve ordered fields while matching names case-insensitively.

    Repeated names remain separate entries in caller order. Original name
    spelling and values are retained for transport-specific serialization;
    collection lookup alone applies the case-insensitive name semantics.
    """

    values: tuple[HeaderField, ...] = ()
    """Ordered header fields, including every repeated name occurrence."""

    def __post_init__(self) -> None:
        """Require immutable storage containing only HeaderField values."""
        values = cast(object, self.values)
        # A tuple prevents collection mutation after construction; validating
        # each member keeps arbitrary objects out before lookup or transport.
        if not isinstance(values, tuple):
            raise TypeError("Headers values must be a tuple.")
        for field in cast(tuple[object, ...], values):
            if not isinstance(field, HeaderField):
                raise TypeError("Headers values must contain HeaderField values.")

    def get_all(self, name: str) -> tuple[str, ...]:
        """Return all values for ``name`` in their original field order.

        Args:
            name: Header name to match without case sensitivity.

        Returns:
            An immutable tuple containing every matching field value.

        Raises:
            TypeError: If ``name`` is not a string.
        """
        candidate = cast(object, name)
        if not isinstance(candidate, str):
            raise TypeError("Header lookup name must be a string.")

        # Header names are case-insensitive while stored field spelling remains
        # untouched. Filtering the tuple also preserves repeated-value order.
        normalized_name = candidate.casefold()
        return tuple(
            field.value
            for field in self.values
            if field.name.casefold() == normalized_name
        )
