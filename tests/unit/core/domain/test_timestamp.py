"""Value-semantics tests for UTC Timestamp values."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import Timestamp


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


def test_timestamp_represents_utc_epoch_and_nanosecond_boundaries() -> None:
    """Verify epoch identity and the full normalized fractional range."""
    epoch = Timestamp(0)
    final_nanosecond = Timestamp(0, 999_999_999)
    before_epoch = Timestamp(-1, 500_000_000)

    assert epoch.epoch_seconds == 0
    assert epoch.nanosecond == 0
    assert final_nanosecond.nanosecond == 999_999_999
    assert before_epoch == Timestamp(epoch_seconds=-1, nanosecond=500_000_000)


def test_timestamp_has_ordered_immutable_value_semantics() -> None:
    """Verify equality, ordering, hashing, and immutability use both fields."""
    earlier = Timestamp(10, 20)
    same = Timestamp(10, 20)
    later_fraction = Timestamp(10, 21)
    later_second = Timestamp(11)

    assert earlier == same
    assert hash(earlier) == hash(same)
    assert earlier < later_fraction < later_second
    _assert_raises(
        FrozenInstanceError,
        lambda: earlier.__setattr__("nanosecond", 22),
        "cannot assign to field",
    )


def test_timestamp_rejects_noncanonical_nanoseconds() -> None:
    """Verify fractional seconds are normalized into one second."""
    for nanosecond in (-1, 1_000_000_000):
        _assert_raises(
            ValueError,
            lambda nanosecond=nanosecond: Timestamp(0, nanosecond),
            "between 0 and 999999999",
        )


def test_timestamp_rejects_non_integer_and_boolean_fields() -> None:
    """Verify fields cannot exploit dynamic or boolean integer coercion."""
    _assert_raises(
        TypeError,
        lambda: Timestamp(cast(int, 1.5)),
        "epoch_seconds must be an integer",
    )
    _assert_raises(
        TypeError,
        lambda: Timestamp(0, cast(int, True)),
        "nanosecond must be an integer",
    )
