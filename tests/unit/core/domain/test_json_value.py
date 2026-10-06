"""Type-contract tests for recursive JsonValue structures."""

from typing import assert_type, get_args, get_origin

from mconet.core.domain import JsonValue


def _accept_json_value(value: JsonValue) -> JsonValue:
    """Expose the recursive alias boundary to Pyright contract checks."""
    return value


def test_json_value_accepts_recursive_arrays_and_objects() -> None:
    """Verify arrays and string-keyed objects can recursively contain JSON."""
    array_value: list[JsonValue] = [None, True, 7, 2.5, "text"]
    object_value: dict[str, JsonValue] = {
        "primitive": "value",
        "array": array_value,
        "object": {"nested": False},
    }

    assert_type(_accept_json_value(array_value), JsonValue)
    assert_type(_accept_json_value(object_value), JsonValue)
    assert _accept_json_value(object_value) is object_value


def test_json_value_uses_only_native_json_collection_shapes() -> None:
    """Verify the recursive public alias does not broaden collection syntax."""
    # Inspect origins instead of repr text so this contract remains stable
    # across every supported Python minor version.
    branches = frozenset(get_args(JsonValue))
    collection_origins = frozenset(
        origin for branch in branches if (origin := get_origin(branch)) is not None
    )

    assert collection_origins == frozenset((list, dict))
    assert tuple not in branches
    assert bytes not in branches
