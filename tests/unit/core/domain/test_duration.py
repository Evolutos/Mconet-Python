"""Value-semantics tests for exact Duration values."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import Duration


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


def test_duration_preserves_zero_positive_and_negative_nanoseconds() -> None:
    """Verify the canonical unit and signed value range are unambiguous."""
    assert Duration(0).total_nanoseconds == 0
    assert Duration(1).total_nanoseconds == 1
    assert Duration(-1).total_nanoseconds == -1


def test_duration_has_ordered_immutable_value_semantics() -> None:
    """Verify equality, ordering, hashing, and immutability use exact content."""
    negative = Duration(-10)
    zero = Duration(0)
    positive = Duration(10)

    assert negative < zero < positive
    assert positive == Duration(10)
    assert hash(positive) == hash(Duration(10))
    _assert_raises(
        FrozenInstanceError,
        lambda: positive.__setattr__("total_nanoseconds", 11),
        "cannot assign to field",
    )


def test_duration_preserves_values_beyond_fixed_width_storage() -> None:
    """Verify construction never wraps or truncates Python integer values."""
    beyond_signed_64_bit = 1 << 63

    assert Duration(beyond_signed_64_bit).total_nanoseconds == beyond_signed_64_bit
    assert Duration(-beyond_signed_64_bit - 1).total_nanoseconds == (
        -beyond_signed_64_bit - 1
    )


def test_duration_rejects_non_integer_and_boolean_values() -> None:
    """Verify dynamic callers cannot introduce lossy or boolean coercion."""
    _assert_raises(
        TypeError,
        lambda: Duration(cast(int, 1.5)),
        "total_nanoseconds must be an integer",
    )
    _assert_raises(
        TypeError,
        lambda: Duration(cast(int, True)),
        "total_nanoseconds must be an integer",
    )
