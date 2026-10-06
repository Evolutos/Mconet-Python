"""Boundary tests for RFC 3339 Timestamp parsing."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import Timestamp, parse_timestamp


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


def test_parse_timestamp_accepts_utc_and_offset_instants() -> None:
    """Verify explicit offsets normalize to the same UTC instant."""
    epoch = Timestamp(0)

    assert parse_timestamp("1970-01-01T00:00:00Z") == epoch
    assert parse_timestamp("1970-01-01T01:30:00+01:30") == epoch
    assert parse_timestamp("1969-12-31T18:30:00-05:30") == epoch


def test_parse_timestamp_preserves_fractional_precision() -> None:
    """Verify one through nine fraction digits become exact nanoseconds."""
    assert parse_timestamp("1970-01-01T00:00:00.1Z") == Timestamp(0, 100_000_000)
    assert parse_timestamp("1970-01-01T00:00:00.000000001Z") == Timestamp(0, 1)
    assert parse_timestamp("1969-12-31T23:59:59.5Z") == Timestamp(-1, 500_000_000)


def test_parse_timestamp_rejects_invalid_syntax_and_precision() -> None:
    """Verify timezone, separators, and fractional precision are explicit."""
    invalid_values = (
        "1970-01-01T00:00:00",
        "1970-01-01t00:00:00z",
        "1970-01-01 00:00:00Z",
        "1970-01-01T00:00:00.Z",
        "1970-01-01T00:00:00.1234567890Z",
    )

    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: parse_timestamp(value),
            "RFC 3339 date-time syntax",
        )


def test_parse_timestamp_rejects_invalid_calendar_values() -> None:
    """Verify impossible dates, leap seconds, and out-of-range times fail."""
    for value in (
        "2023-02-29T00:00:00Z",
        "2024-13-01T00:00:00Z",
        "2024-01-01T24:00:00Z",
        "2024-01-01T00:00:60Z",
    ):
        _assert_raises(
            ValueError,
            lambda value=value: parse_timestamp(value),
            "invalid calendar value",
        )


def test_parse_timestamp_rejects_unknown_or_invalid_offsets() -> None:
    """Verify every accepted offset identifies a concrete UTC instant."""
    _assert_raises(
        ValueError,
        lambda: parse_timestamp("1970-01-01T00:00:00-00:00"),
        "does not identify a UTC instant",
    )
    for value in (
        "1970-01-01T00:00:00+24:00",
        "1970-01-01T00:00:00+00:60",
    ):
        _assert_raises(
            ValueError,
            lambda value=value: parse_timestamp(value),
            "between -23:59 and +23:59",
        )


def test_parse_timestamp_rejects_utc_normalization_overflow() -> None:
    """Verify offset conversion cannot escape the supported UTC year range."""
    for value in (
        "0001-01-01T00:00:00+23:59",
        "9999-12-31T23:59:59-23:59",
    ):
        _assert_raises(
            ValueError,
            lambda value=value: parse_timestamp(value),
            "outside the supported UTC range",
        )


def test_parse_timestamp_requires_string_input() -> None:
    """Verify dynamic callers cannot pass another scalar type."""
    _assert_raises(
        TypeError,
        lambda: parse_timestamp(cast(str, 0)),
        "must be a string",
    )
