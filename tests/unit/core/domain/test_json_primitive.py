"""Type-contract tests for JsonPrimitive."""

from types import NoneType
from typing import assert_type, get_args

from mconet.core.domain import JsonPrimitive


def _accept_json_primitive(value: JsonPrimitive) -> JsonPrimitive:
    """Expose the alias boundary to Pyright for positive contract checks."""
    return value


def test_json_primitive_accepts_exact_json_scalar_categories() -> None:
    """Verify null, boolean, integer, floating-point, and string typecheck."""
    assert_type(_accept_json_primitive(None), JsonPrimitive)
    assert_type(_accept_json_primitive(False), JsonPrimitive)
    assert_type(_accept_json_primitive(42), JsonPrimitive)
    assert_type(_accept_json_primitive(3.5), JsonPrimitive)
    assert_type(_accept_json_primitive("value"), JsonPrimitive)


def test_json_primitive_excludes_structured_and_binary_categories() -> None:
    """Verify the runtime alias contains no array, object, or binary branch."""
    # Exact member inspection complements Pyright's positive calls without
    # adding intentionally invalid source that would break the strict suite.
    assert frozenset(get_args(JsonPrimitive)) == frozenset(
        (NoneType, bool, int, float, str)
    )
