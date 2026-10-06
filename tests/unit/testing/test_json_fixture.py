"""Canonical comparison tests for decoded JSON fixtures."""

import math
from collections.abc import Callable
from typing import cast

from mconet.core.domain import JsonValue
from mconet.testing import json_fixtures_equal


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_json_fixture_comparison_ignores_object_key_order() -> None:
    """Verify nested object insertion order does not affect equality."""
    actual: JsonValue = {
        "metadata": {"region": "east", "priority": 2},
        "items": [{"id": "a", "enabled": True}],
    }
    expected: JsonValue = {
        "items": [{"enabled": True, "id": "a"}],
        "metadata": {"priority": 2.0, "region": "east"},
    }

    # Integer and floating-point forms belong to the same JSON number kind, and
    # safe-range validation guarantees exact comparison for integral values.
    assert json_fixtures_equal(actual, expected)


def test_json_fixture_comparison_preserves_array_order_and_primitive_kinds() -> None:
    """Verify arrays stay ordered and booleans never compare as numbers."""
    assert not json_fixtures_equal([1, 2], [2, 1])
    assert not json_fixtures_equal(True, 1)
    assert not json_fixtures_equal(None, "null")
    assert json_fixtures_equal(-0.0, 0)


def test_json_fixture_comparison_detects_shape_and_value_mismatches() -> None:
    """Verify object keys, array lengths, and scalar values all participate."""
    assert not json_fixtures_equal({"value": 1}, {"other": 1})
    assert not json_fixtures_equal([1], [1, 2])
    assert not json_fixtures_equal({"value": "a"}, {"value": "b"})
    assert not json_fixtures_equal({"value": []}, {"value": {}})


def test_json_fixture_comparison_rejects_invalid_inputs() -> None:
    """Verify malformed structures and numbers are errors, not mismatches."""
    _assert_raises(
        TypeError,
        lambda: json_fixtures_equal(cast(JsonValue, (1, 2)), [1, 2]),
        "structurally valid JsonValue",
    )
    for value in (2**53, math.nan, math.inf):
        _assert_raises(
            ValueError,
            lambda value=value: json_fixtures_equal(cast(JsonValue, value), 0),
            "JSON",
        )


def test_json_fixture_comparison_handles_deep_nesting_iteratively() -> None:
    """Verify valid fixture depth does not depend on the recursion limit."""
    actual: JsonValue = "leaf"
    expected: JsonValue = "leaf"
    # Build separate but equivalent structures so identity cannot short-circuit
    # the comparator and every array level is visited.
    for _ in range(2_000):
        actual = [actual]
        expected = [expected]

    assert json_fixtures_equal(actual, expected)
