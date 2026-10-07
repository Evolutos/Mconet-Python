"""Private recursion-independent snapshots for validated JSON values."""

from __future__ import annotations

from typing import TypeAlias, cast

from mconet.core.domain import JsonValue, validate_json_value_numbers

JsonValueSnapshot: TypeAlias = tuple[tuple[str, object], ...]
"""Canonical immutable event sequence representing one JSON value."""


def snapshot_json_value(value: JsonValue) -> JsonValueSnapshot:
    """Validate and snapshot one JSON value without recursive Python calls.

    Args:
        value: Portable JSON value whose complete current state is required.

    Returns:
        An immutable type-tagged traversal independent of object key order.

    Raises:
        TypeError: If ``value`` is not structurally valid JSON data.
        ValueError: If ``value`` contains a non-portable JSON number.
    """
    # Shared validation rejects cycles and unsupported objects before traversal,
    # making every remaining branch a built-in JSON container or primitive.
    validate_json_value_numbers(value)
    pending: list[tuple[str, object]] = [("value", value)]
    events: list[tuple[str, object]] = []

    while pending:
        action, current = pending.pop()
        if action == "key":
            # A distinct tag prevents an object member name from colliding with
            # an ordinary string value at the same traversal position.
            events.append(("key", current))
            continue
        if isinstance(current, dict):
            mapping = cast(dict[str, object], current)
            events.append(("object", len(mapping)))
            # Sorted keys make mapping insertion order irrelevant. Reverse push
            # order preserves ascending key order when the LIFO stack is read.
            for key in reversed(sorted(mapping)):
                pending.append(("value", mapping[key]))
                pending.append(("key", key))
            continue
        if isinstance(current, list):
            sequence = cast(list[object], current)
            events.append(("array", len(sequence)))
            # Array order remains semantic, so reverse insertion restores the
            # original order during iterative traversal.
            pending.extend(("value", item) for item in reversed(sequence))
            continue
        if isinstance(current, bool):
            # bool precedes number because Python bool is an int subclass while
            # JSON models the two primitive kinds independently.
            events.append(("boolean", current))
            continue
        if type(current) in (int, float):
            # JSON has one number kind. Python equality deliberately treats a
            # portable integer and its equal floating-point representation alike.
            events.append(("number", current))
            continue
        if current is None:
            events.append(("null", None))
            continue
        if isinstance(current, str):
            events.append(("string", current))
            continue
        # This branch is unreachable after shared validation, but fail closed
        # without rendering a caller-controlled value if that invariant changes.
        raise TypeError("validated value contains unsupported JSON data.")

    return tuple(events)
