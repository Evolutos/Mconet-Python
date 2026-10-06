"""Recursive values representable by the language-neutral JSON data model."""

from __future__ import annotations

import math
from typing import TypeAlias, cast

from mconet.core.domain.json_primitive import JsonPrimitive

# Concrete list and dict branches match Python's native JSON representation
# without accidentally admitting tuples, bytes, or arbitrary collection types.
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
"""A recursive JSON primitive, array, or string-keyed object."""

_MIN_SAFE_INTEGER = -(2**53 - 1)
_MAX_SAFE_INTEGER = 2**53 - 1


def is_json_value(value: object) -> bool:
    """Check recursive JSON structure without applying numeric policies."""
    # Enter/leave markers provide depth-first cycle detection without relying
    # on Python recursion, while still allowing the same container in siblings.
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
        # Numeric range is deliberately deferred so structural callers can
        # distinguish invalid JSON shapes from portability policy failures.
        if current is None or isinstance(current, (bool, int, float, str)):
            continue
        return False
    return True


def validate_json_value_numbers(value: JsonValue) -> JsonValue:
    """Validate portable numeric values throughout a recursive JSON value.

    Integers use the inclusive interoperable range ``-(2**53 - 1)`` through
    ``2**53 - 1`` so TypeScript and other binary64-based consumers retain them
    exactly. Floating-point values must be finite IEEE 754 binary64 values;
    NaN and positive or negative infinity are not JSON numbers.

    Args:
        value: A primitive, array, or string-keyed object to validate.

    Returns:
        The original value after successful recursive validation.

    Raises:
        TypeError: If ``value`` is not structurally a :class:`JsonValue`.
        ValueError: If an integer is unsafe or a float is non-finite.
    """
    candidate = cast(object, value)
    # Validate shape and cycles once before the numeric walk. Every remaining
    # container is therefore a concrete list or string-keyed dictionary.
    if not is_json_value(candidate):
        raise TypeError("value must be a structurally valid JsonValue.")

    pending: list[object] = [candidate]
    while pending:
        current = pending.pop()
        # bool precedes int because Python models bool as an int subclass while
        # JSON defines booleans as a separate primitive kind.
        if isinstance(current, bool) or current is None or isinstance(current, str):
            continue
        if isinstance(current, int):
            if not _MIN_SAFE_INTEGER <= current <= _MAX_SAFE_INTEGER:
                raise ValueError(
                    "JSON integer must be within the interoperable safe range."
                )
            continue
        if isinstance(current, float):
            if not math.isfinite(current):
                raise ValueError("JSON floating-point value must be finite.")
            continue
        # Push child values only; object keys were already checked as strings by
        # the structural pass and never participate in numeric validation.
        if isinstance(current, list):
            pending.extend(cast(list[object], current))
            continue
        mapping = cast(dict[str, object], current)
        pending.extend(mapping.values())
    return value
