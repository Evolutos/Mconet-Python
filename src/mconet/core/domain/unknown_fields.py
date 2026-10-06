"""Lossless handling of unknown JSON object fields."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers


def preserve_unknown_fields(
    fields: Mapping[str, JsonValue],
    known_field_names: Collection[str],
) -> Extensions:
    """Capture fields not understood by the current schema implementation.

    Field names and values are retained exactly in encounter order. The result
    exposes a read-only mapping snapshot so later additions or removals in the
    input mapping cannot change which fields were preserved. Values are not
    interpreted and therefore cannot affect component selection or control
    flow.

    Args:
        fields: A decoded JSON object containing known and unknown fields.
        known_field_names: Names consumed by the current schema implementation.

    Returns:
        A read-only mapping containing only unknown fields.

    Raises:
        TypeError: If a mapping or field-name contract is violated.
    """
    source = _require_field_mapping(fields, "fields")
    known_names = _require_field_names(known_field_names)
    preserved = {
        name: value for name, value in source.items() if name not in known_names
    }
    return MappingProxyType(preserved)


def restore_preserved_fields(
    known_fields: Mapping[str, JsonValue],
    preserved_fields: Extensions,
) -> Extensions:
    """Merge known fields with preserved unknown fields for serialization.

    A collision is rejected rather than choosing one value, because overwriting
    either side would silently lose data when a field becomes known in a later
    schema implementation.

    Args:
        known_fields: Fields serialized by the current implementation.
        preserved_fields: Unknown fields retained during decoding.

    Returns:
        A read-only mapping snapshot containing both field sets.

    Raises:
        TypeError: If either mapping contains a non-string key.
        ValueError: If a field name occurs in both mappings.
    """
    known = _require_field_mapping(known_fields, "known_fields")
    preserved = _require_field_mapping(preserved_fields, "preserved_fields")
    collisions = known.keys() & preserved.keys()
    if collisions:
        first_collision = min(collisions)
        raise ValueError(
            f"Preserved field collides with known field: {first_collision}."
        )

    restored = dict(known)
    restored.update(preserved)
    return MappingProxyType(restored)


def _require_field_mapping(
    value: Mapping[str, JsonValue],
    field: str,
) -> Mapping[str, JsonValue]:
    """Require a mapping whose runtime keys satisfy the JSON object contract."""
    candidate = cast(object, value)
    if not isinstance(candidate, Mapping):
        raise TypeError(f"{field} must be a mapping.")
    mapping = cast(Mapping[object, object], candidate)
    if any(not isinstance(name, str) for name in mapping):
        raise TypeError(f"{field} keys must be strings.")
    typed_mapping = cast(Mapping[str, JsonValue], mapping)
    for json_value in typed_mapping.values():
        validate_json_value_numbers(json_value)
    return typed_mapping


def _require_field_names(value: Collection[str]) -> frozenset[str]:
    """Require a non-text collection containing only string field names."""
    candidate = cast(object, value)
    if not isinstance(candidate, Collection) or isinstance(candidate, str):
        raise TypeError("known_field_names must be a collection of strings.")
    names = cast(Collection[object], candidate)
    if any(not isinstance(name, str) for name in names):
        raise TypeError("known_field_names must contain only strings.")
    return frozenset(cast(Collection[str], names))
