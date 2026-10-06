"""Portable integer and floating-point tests for recursive JsonValue data."""

import json
import math
import sys
from collections.abc import Callable
from typing import cast

from mconet.core.domain import JsonValue, validate_json_value_numbers

_MIN_SAFE_INTEGER = -(2**53 - 1)
_MAX_SAFE_INTEGER = 2**53 - 1


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


def test_json_number_validator_accepts_safe_integer_boundaries() -> None:
    """Verify both interoperable integer endpoints remain exact."""
    value: JsonValue = {
        "minimum": _MIN_SAFE_INTEGER,
        "maximum": _MAX_SAFE_INTEGER,
        "zero": 0,
        "boolean": True,
    }

    assert validate_json_value_numbers(value) is value
    assert json.loads(json.dumps(value)) == value


def test_json_number_validator_rejects_unsafe_integers_recursively() -> None:
    """Verify overflow fails at top level and inside arrays or objects."""
    invalid_values: tuple[JsonValue, ...] = (
        _MIN_SAFE_INTEGER - 1,
        _MAX_SAFE_INTEGER + 1,
        [0, {"overflow": _MAX_SAFE_INTEGER + 1}],
    )

    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: validate_json_value_numbers(value),
            "interoperable safe range",
        )


def test_json_number_validator_accepts_finite_binary64_values() -> None:
    """Verify ordinary, extreme, subnormal, and signed-zero floats are valid."""
    negative_zero = -0.0
    value: JsonValue = [
        1.5,
        sys.float_info.max,
        sys.float_info.min,
        math.ulp(0.0),
        negative_zero,
    ]

    assert validate_json_value_numbers(value) is value
    assert math.copysign(1.0, cast(list[float], value)[-1]) == -1.0
    json.dumps(value, allow_nan=False)


def test_json_number_validator_rejects_non_finite_floats() -> None:
    """Verify NaN and both infinities cannot enter JSON data."""
    for value in (math.nan, math.inf, -math.inf):
        _assert_raises(
            ValueError,
            lambda value=value: validate_json_value_numbers(value),
            "must be finite",
        )


def test_json_number_validator_requires_json_structure() -> None:
    """Verify tuples, non-string keys, and cycles fail before numeric traversal."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    invalid_values = (
        cast(JsonValue, (1, 2)),
        cast(JsonValue, {1: 2}),
        cast(JsonValue, cyclic),
    )

    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: validate_json_value_numbers(value),
            "structurally valid JsonValue",
        )
