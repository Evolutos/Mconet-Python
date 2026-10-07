"""Exact advancement and deterministic deadline tests for FakeClock."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import Duration, Timestamp
from mconet.testing import FakeClock


def test_fake_clock_returns_exact_initial_timestamp_without_hidden_ticks() -> None:
    """Preserve explicit initial identity across repeated passive reads."""
    initial = Timestamp(1_800_000_000, 123_456_789)
    clock = FakeClock(initial)

    first = clock.now()
    second = clock.now()

    # Identity and value stability prove reads do not sample wall time, round
    # precision, increment an implicit tick, or replace the immutable value.
    assert first is initial
    assert second is initial
    assert first == Timestamp(1_800_000_000, 123_456_789)


def test_fake_clock_advances_across_second_boundary_exactly() -> None:
    """Normalize fractional carry without float precision loss."""
    clock = FakeClock(Timestamp(10, 900_000_000))

    result = clock.advance(Duration(250_000_001))

    # Advance is a state operation with no return value; the new canonical pair
    # contains the exact carried seconds and remaining fractional nanoseconds.
    assert result is None
    assert clock.now() == Timestamp(11, 150_000_001)


def test_fake_clock_advances_pre_epoch_timestamp_with_floor_semantics() -> None:
    """Cross the Unix epoch while retaining canonical negative-time behavior."""
    clock = FakeClock(Timestamp(-1, 900_000_000))

    clock.advance(Duration(200_000_000))

    # -0.1 seconds plus 0.2 seconds is +0.1 seconds; integer divmod preserves the
    # Timestamp rule that fractions are always non-negative.
    assert clock.now() == Timestamp(0, 100_000_000)


def test_fake_clock_zero_advance_preserves_current_identity() -> None:
    """Treat zero duration as an observable identity-preserving no-op."""
    current = Timestamp(77, 42)
    clock = FakeClock(current)

    clock.advance(Duration(0))

    # No-op advancement must not allocate a replacement or introduce a tick.
    assert clock.now() is current


def test_fake_clock_supports_repeatable_deadline_comparisons() -> None:
    """Reach a deadline through explicit increments with no real waiting."""
    start = Timestamp(100, 750_000_000)
    deadline = Timestamp(102, 250_000_000)
    clock = FakeClock(start)

    clock.advance(Duration(1_000_000_000))
    before_deadline = clock.now()
    clock.advance(Duration(500_000_000))
    at_deadline = clock.now()

    # The caller owns deadline policy; deterministic clock values make the same
    # comparison repeatable without sleep, polling, timezone, or scheduler state.
    assert before_deadline == Timestamp(101, 750_000_000)
    assert before_deadline < deadline
    assert at_deadline is clock.now()
    assert at_deadline == deadline
    assert at_deadline >= deadline


def test_fake_clock_preserves_arbitrary_exact_integer_arithmetic() -> None:
    """Advance beyond fixed-width storage without wrapping or truncation."""
    clock = FakeClock(Timestamp(-(10**30), 999_999_999))
    duration = Duration(2 * 10**39 + 2)

    clock.advance(duration)

    # Python integer arithmetic mirrors Timestamp and Duration value semantics;
    # the fake adds exactly rather than imposing an undocumented platform range.
    expected_total = -(10**30) * 1_000_000_000 + 999_999_999
    expected_total += duration.total_nanoseconds
    expected_seconds, expected_fraction = divmod(expected_total, 1_000_000_000)
    assert clock.now() == Timestamp(expected_seconds, expected_fraction)


def test_fake_clock_rejects_invalid_inputs_without_changing_time() -> None:
    """Reject invalid construction, dynamic duration values, and time reversal."""
    initial = Timestamp(100, 200)
    clock = FakeClock(initial)
    invalid_calls: tuple[tuple[Callable[[], object], type[BaseException], str], ...] = (
        (
            lambda: FakeClock(cast(Timestamp, object())),
            TypeError,
            "initial must be a Timestamp",
        ),
        (
            lambda: clock.advance(cast(Duration, object())),
            TypeError,
            "duration must be a Duration",
        ),
        (
            lambda: clock.advance(Duration(-1)),
            ValueError,
            "duration must not be negative",
        ),
    )

    for action, exception_type, message in invalid_calls:
        try:
            action()
        except exception_type as error:
            # Stable diagnostics ensure malformed setup cannot masquerade as an
            # expected deadline or timeout branch in a higher-level test.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid FakeClock usage to fail.")

    # Both failed advance calls leave the original immutable time untouched.
    assert clock.now() is initial


def test_fake_clock_has_exact_minimal_surface() -> None:
    """Expose only passive reads and explicit forward advancement."""
    clock = FakeClock(Timestamp(0))
    now = FakeClock.now
    advance = FakeClock.advance

    # Concrete annotations and synchronous behavior define the complete public
    # surface without introducing a production clock protocol in this step.
    assert tuple(inspect.signature(now).parameters) == ("self",)
    assert get_type_hints(now) == {"return": Timestamp}
    assert tuple(inspect.signature(advance).parameters) == ("self", "duration")
    assert get_type_hints(advance) == {
        "duration": Duration,
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(now)
    assert not inspect.iscoroutinefunction(advance)

    # Deadline policy, scheduling, sleeping, reset, absolute set, and system-time
    # sampling remain outside this deterministic value source.
    for forbidden_member in (
        "deadline_reached",
        "schedule",
        "sleep",
        "reset",
        "set",
        "utcnow",
        "time",
    ):
        assert not hasattr(clock, forbidden_member)
