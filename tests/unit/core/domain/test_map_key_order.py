"""Order-independent object-key tests for JSON domain mappings."""

import json

from mconet.core.domain import (
    JsonValue,
    OptionalField,
    preserve_unknown_fields,
    restore_preserved_fields,
    serialize_optional_fields,
)


def test_json_object_equality_ignores_key_insertion_order() -> None:
    """Verify object keys are unordered while nested array order remains data."""
    first: JsonValue = {
        "metadata": {"region": "east", "priority": 2},
        "items": ["first", "second"],
    }
    reordered: JsonValue = {
        "items": ["first", "second"],
        "metadata": {"priority": 2, "region": "east"},
    }
    reversed_array: JsonValue = {
        "metadata": {"priority": 2, "region": "east"},
        "items": ["second", "first"],
    }

    # JSON text can reflect producer insertion order, but decoded object
    # semantics use mapping equality and therefore ignore object-key order.
    assert json.dumps(first) != json.dumps(reordered)
    assert first == reordered
    assert first != reversed_array


def test_unknown_field_semantics_ignore_key_insertion_order() -> None:
    """Verify preservation and restoration do not assign meaning to key order."""
    first = preserve_unknown_fields(
        {"known": 1, "futureA": "a", "futureB": "b"},
        {"known"},
    )
    reordered = preserve_unknown_fields(
        {"futureB": "b", "known": 1, "futureA": "a"},
        {"known"},
    )

    # Implementations may retain encounter order for deterministic re-emission,
    # but mapping equality is the business contract used for field semantics.
    assert tuple(first) != tuple(reordered)
    assert first == reordered
    assert restore_preserved_fields({"known": 1}, first) == (
        restore_preserved_fields({"known": 1}, reordered)
    )


def test_optional_serialization_semantics_ignore_key_insertion_order() -> None:
    """Verify presence-aware output equality is independent of source order."""
    first = serialize_optional_fields(
        {
            "alpha": OptionalField(True, 1),
            "omitted": OptionalField(False),
            "beta": OptionalField(True, 2),
        }
    )
    reordered = serialize_optional_fields(
        {
            "beta": OptionalField(True, 2),
            "omitted": OptionalField(False),
            "alpha": OptionalField(True, 1),
        }
    )

    # Presence filtering may produce a different iteration order, but the
    # resulting JSON object carries the same fields and values.
    assert tuple(first) != tuple(reordered)
    assert first == reordered == {"alpha": 1, "beta": 2}
