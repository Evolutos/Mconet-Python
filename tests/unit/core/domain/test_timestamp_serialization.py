"""Exact precision tests for canonical Timestamp serialization."""

from collections.abc import Callable
from typing import Literal, cast

from mconet.core.domain import Timestamp, parse_timestamp, serialize_timestamp

TimestampPrecision = Literal["seconds", "milliseconds", "microseconds", "nanoseconds"]


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


def test_timestamp_serialization_uses_fixed_utc_precision() -> None:
    """Verify every supported precision has one canonical UTC representation."""
    timestamp = Timestamp(0, 123_456_789)

    assert serialize_timestamp(Timestamp(0), "seconds") == "1970-01-01T00:00:00Z"
    assert (
        serialize_timestamp(Timestamp(0, 123_000_000), "milliseconds")
        == "1970-01-01T00:00:00.123Z"
    )
    assert (
        serialize_timestamp(Timestamp(0, 123_456_000), "microseconds")
        == "1970-01-01T00:00:00.123456Z"
    )
    assert serialize_timestamp(timestamp) == "1970-01-01T00:00:00.123456789Z"


def test_timestamp_serialization_preserves_negative_instants() -> None:
    """Verify epoch-floor storage converts to the preceding UTC second."""
    timestamp = Timestamp(-1, 500_000_000)

    serialized = serialize_timestamp(timestamp, "milliseconds")

    assert serialized == "1969-12-31T23:59:59.500Z"
    assert parse_timestamp(serialized) == timestamp


def test_timestamp_serialization_rejects_precision_loss() -> None:
    """Verify coarser output never truncates or rounds fractional data."""
    cases = (
        (Timestamp(0, 1), "microseconds"),
        (Timestamp(0, 1_000), "milliseconds"),
        (Timestamp(0, 1_000_000), "seconds"),
    )

    for timestamp, precision in cases:
        _assert_raises(
            ValueError,
            lambda timestamp=timestamp, precision=precision: serialize_timestamp(
                timestamp,
                cast(TimestampPrecision, precision),
            ),
            "requested precision",
        )


def test_timestamp_serialization_round_trips_calendar_boundaries() -> None:
    """Verify four-digit RFC 3339 year endpoints preserve exact instants."""
    for text in (
        "0001-01-01T00:00:00.000000001Z",
        "9999-12-31T23:59:59.999999999Z",
    ):
        timestamp = parse_timestamp(text)
        assert serialize_timestamp(timestamp) == text


def test_timestamp_serialization_rejects_invalid_arguments_and_range() -> None:
    """Verify runtime types, precision names, and calendar range are bounded."""
    _assert_raises(
        TypeError,
        lambda: serialize_timestamp(cast(Timestamp, "1970-01-01T00:00:00Z")),
        "must be a Timestamp",
    )
    _assert_raises(
        TypeError,
        lambda: serialize_timestamp(Timestamp(0), cast(TimestampPrecision, 9)),
        "precision must be a string",
    )
    _assert_raises(
        ValueError,
        lambda: serialize_timestamp(Timestamp(0), cast(TimestampPrecision, "minutes")),
        "Unsupported Timestamp precision",
    )
    for timestamp in (Timestamp(-(10**30)), Timestamp(10**30)):
        _assert_raises(
            ValueError,
            lambda timestamp=timestamp: serialize_timestamp(timestamp),
            "four-digit year range",
        )
