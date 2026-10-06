"""Recursive values representable by the language-neutral JSON data model."""

from __future__ import annotations

from typing import TypeAlias, cast

from mconet.core.domain.json_primitive import JsonPrimitive

# Concrete list and dict branches match Python's native JSON representation
# without accidentally admitting tuples, bytes, or arbitrary collection types.
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
"""A recursive JSON primitive, array, or string-keyed object."""


def is_json_value(value: object) -> bool:
    """Check recursive JSON structure without applying numeric policies."""
    pending: list[tuple[object, bool]] = [(value, False)]
    active_containers: set[int] = set()
    while pending:
        current, leaving = pending.pop()
        if leaving:
            active_containers.remove(id(current))
            continue
        if isinstance(current, list):
            sequence = cast(list[object], current)
            identity = id(sequence)
            if identity in active_containers:
                return False
            active_containers.add(identity)
            pending.append((sequence, True))
            pending.extend((item, False) for item in reversed(sequence))
            continue
        if isinstance(current, dict):
            mapping = cast(dict[object, object], current)
            identity = id(mapping)
            if identity in active_containers:
                return False
            active_containers.add(identity)
            pending.append((mapping, True))
            if any(not isinstance(key, str) for key in mapping):
                return False
            pending.extend((item, False) for item in reversed(tuple(mapping.values())))
            continue
        if current is None or isinstance(current, (bool, int, float, str)):
            continue
        return False
    return True
