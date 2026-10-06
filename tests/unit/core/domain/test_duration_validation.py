"""Boundary tests for exact Duration conversion and validation."""

from collections.abc import Callable
from typing import Literal, cast

from mconet.core.domain import Duration, validate_duration

_DurationUnit = Literal["seconds", "milliseconds", "microseconds", "nanoseconds"]


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


def test_validate_duration_converts_supported_units_exactly() -> None:
    """Verify every source unit maps to the same canonical nanoseconds."""
    expected = Duration(1_000_000_000)

    assert validate_duration(1, "seconds") == expected
    assert validate_duration(1_000, "milliseconds") == expected
    assert validate_duration(1_000_000, "microseconds") == expected
    assert validate_duration(1_000_000_000, "nanoseconds") == expected
    assert validate_duration(-2, "milliseconds") == Duration(-2_000_000)


def test_validate_duration_accepts_signed_64_bit_boundaries() -> None:
    """Verify both inclusive portable range endpoints remain exact."""
    minimum = -(1 << 63)
    maximum = (1 << 63) - 1

    assert validate_duration(minimum) == Duration(minimum)
    assert validate_duration(maximum) == Duration(maximum)


def test_validate_duration_rejects_conversion_overflow() -> None:
    """Verify direct and unit-scaled values cannot exceed portable storage."""
    invalid_values: tuple[tuple[int, _DurationUnit], ...] = (
        ((1 << 63), "nanoseconds"),
        (-(1 << 63) - 1, "nanoseconds"),
        ((1 << 63) // 1_000_000_000 + 1, "seconds"),
    )

    for value, unit in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value, unit=unit: validate_duration(value, unit),
            "signed 64-bit nanosecond range",
        )


def test_validate_duration_rejects_lossy_numeric_inputs() -> None:
    """Verify validation never rounds floats or treats booleans as integers."""
    for value in (1.5, True):
        _assert_raises(
            TypeError,
            lambda value=value: validate_duration(cast(int, value)),
            "value must be an integer",
        )


def test_validate_duration_rejects_invalid_units() -> None:
    """Verify unit spelling is explicit and cannot trigger implicit conversion."""
    _assert_raises(
        ValueError,
        lambda: validate_duration(1, cast(_DurationUnit, "minutes")),
        "Unsupported Duration unit",
    )
    _assert_raises(
        TypeError,
        lambda: validate_duration(1, cast(_DurationUnit, 1)),
        "unit must be a string",
    )
