"""Value and boundary tests for factual RecoveryHint metadata."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import Duration, RecoveryHint


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


def test_recovery_hint_represents_retry_and_processing_facts() -> None:
    """Verify permanent, immediate, delayed, and processing states are distinct."""
    permanent = RecoveryHint(
        transient=False,
        request_may_have_been_processed=False,
    )
    immediate = RecoveryHint(transient=True)
    delayed = RecoveryHint(
        transient=True,
        retry_after=Duration(2_000_000_000),
        request_may_have_been_processed=True,
    )

    assert permanent.retry_after is None
    assert permanent.request_may_have_been_processed is False
    assert immediate.request_may_have_been_processed is None
    assert delayed.retry_after == Duration(2_000_000_000)
    assert delayed.request_may_have_been_processed is True


def test_recovery_hint_accepts_zero_retry_delay() -> None:
    """Verify an explicitly immediate retry is different from an absent hint."""
    hint = RecoveryHint(transient=True, retry_after=Duration(0))

    assert hint.retry_after == Duration(0)


def test_recovery_hint_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability include every fact field."""
    first = RecoveryHint(True, Duration(1), None)
    same = RecoveryHint(True, Duration(1), None)
    processed = RecoveryHint(True, Duration(1), True)

    assert first == same
    assert hash(first) == hash(same)
    assert first != processed
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("transient", False),
        "cannot assign to field",
    )


def test_recovery_hint_rejects_invalid_field_types() -> None:
    """Verify dynamic inputs cannot exploit truthiness or untyped delays."""
    _assert_raises(
        TypeError,
        lambda: RecoveryHint(cast(bool, 1)),
        "transient must be a boolean",
    )
    _assert_raises(
        TypeError,
        lambda: RecoveryHint(True, cast(Duration, 1)),
        "retry_after must be a Duration or None",
    )
    _assert_raises(
        TypeError,
        lambda: RecoveryHint(True, request_may_have_been_processed=cast(bool, 1)),
        "must be a boolean or None",
    )


def test_recovery_hint_rejects_invalid_retry_delays() -> None:
    """Verify retry delay is non-negative, portable, and only for transient errors."""
    _assert_raises(
        ValueError,
        lambda: RecoveryHint(True, Duration(-1)),
        "must not be negative",
    )
    _assert_raises(
        ValueError,
        lambda: RecoveryHint(True, Duration(1 << 63)),
        "signed 64-bit nanosecond range",
    )
    _assert_raises(
        ValueError,
        lambda: RecoveryHint(False, Duration(1)),
        "requires a transient failure",
    )
