"""Presence-aware JSON fields for lossless optional serialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import (
    JsonValue,
    is_json_value,
    validate_json_value_numbers,
)


@dataclass(frozen=True, slots=True)
class OptionalField:
    """Distinguish an omitted field from a present JSON value.

    ``is_present=False`` represents a missing field and requires ``value=None``.
    ``is_present=True`` represents an explicitly supplied value, including JSON
    null, an empty collection, or a value equal to its schema default.
    """

    is_present: bool
    """Whether the field occurred in the source or was explicitly supplied."""

    value: JsonValue = None
    """The present JSON value, or ``None`` storage for a missing field."""

    def __post_init__(self) -> None:
        """Require a valid presence flag and JSON value state."""
        present = cast(object, self.is_present)
        value = cast(object, self.value)
        # Exact bool checking prevents integer truthiness from changing whether
        # a field is emitted.
        if type(present) is not bool:
            raise TypeError("OptionalField is_present must be a boolean.")
        # The missing state has one canonical representation; present null is
        # represented separately by is_present=True with value=None.
        if not present:
            if value is not None:
                raise ValueError("A missing OptionalField cannot contain a value.")
            return
        # Present values must satisfy both JSON shape and portable number rules
        # before they can reach serialization.
        if not is_json_value(value):
            raise TypeError("A present OptionalField value must be a JsonValue.")
        validate_json_value_numbers(cast(JsonValue, value))


def serialize_optional_fields(
    fields: Mapping[str, OptionalField],
) -> Extensions:
    """Serialize present fields while omitting only explicitly missing fields.

    Present JSON nulls, empty collections, and values equal to schema defaults
    are retained. The result is a read-only mapping snapshot.

    Args:
        fields: Field names paired with explicit presence-aware values.

    Returns:
        A read-only JSON object containing every present field.

    Raises:
        TypeError: If the input is not a string-keyed OptionalField mapping.
    """
    candidate = cast(object, fields)
    if not isinstance(candidate, Mapping):
        raise TypeError("fields must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    serialized: dict[str, JsonValue] = {}
    # Presence is the only omission criterion; nulls, defaults, and empty
    # collections remain observable values.
    for name, field in source.items():
        if not isinstance(name, str):
            raise TypeError("fields keys must be strings.")
        if not isinstance(field, OptionalField):
            raise TypeError("fields values must be OptionalField instances.")
        if field.is_present:
            serialized[name] = field.value
    # Snapshot the selected members so later source-mapping changes cannot
    # alter serialized output.
    return MappingProxyType(serialized)
