"""Lifecycle and concurrency tests for ControllableCancellationSignal."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from threading import Barrier, Thread
from typing import cast, get_type_hints

from mconet.core.domain import CancellationSignal
from mconet.testing import ControllableCancellationSignal


def test_signal_structurally_implements_active_cancellation_contract() -> None:
    """Start active and satisfy the read-only structural protocol."""
    signal = ControllableCancellationSignal()

    accepted: CancellationSignal = signal

    # Static and runtime protocol checks recognize the same ordinary instance;
    # the test-only cancel operation does not enter the consumer protocol.
    assert accepted is signal
    assert isinstance(signal, CancellationSignal)
    assert signal.is_cancelled is False
    assert signal.reason is None


def test_signal_delivers_execution_time_cancellation_once_in_order() -> None:
    """Notify pending callbacks once and retain the first reason."""
    signal = ControllableCancellationSignal()
    deliveries: list[tuple[str, str | None]] = []
    signal.subscribe(lambda reason: deliveries.append(("first", reason)))
    signal.subscribe(lambda reason: deliveries.append(("second", reason)))

    first_result = signal.cancel("caller_requested")
    second_result = signal.cancel("later_reason")

    # The first transition commits state and registration-order delivery; later
    # requests return without replacing reason or notifying either callback.
    assert first_result is None
    assert second_result is None
    assert signal.is_cancelled is True
    assert signal.reason == "caller_requested"
    assert deliveries == [
        ("first", "caller_requested"),
        ("second", "caller_requested"),
    ]


def test_signal_delivers_pre_cancellation_synchronously() -> None:
    """Notify a late subscriber before subscribe returns with stable reason."""
    signal = ControllableCancellationSignal()
    signal.cancel()
    deliveries: list[str | None] = []

    unsubscribe = signal.subscribe(deliveries.append)

    # Delivery has already completed when subscribe returns; the remover owns no
    # pending state and remains safe across repeated cleanup calls.
    assert deliveries == [None]
    assert signal.is_cancelled is True
    assert signal.reason is None
    unsubscribe()
    unsubscribe()
    assert deliveries == [None]


def test_signal_unsubscribe_is_idempotent_before_and_after_delivery() -> None:
    """Remove only pending work and tolerate cleanup after notification."""
    signal = ControllableCancellationSignal()
    removed: list[str | None] = []
    delivered: list[str | None] = []
    remove_first = signal.subscribe(removed.append)
    remove_second = signal.subscribe(delivered.append)

    remove_first()
    remove_first()
    signal.cancel("completed")
    remove_first()
    remove_second()
    remove_second()

    # The removed callback stays silent; cleanup retained by a delivered
    # subscriber cannot duplicate or erase the completed notification.
    assert removed == []
    assert delivered == ["completed"]


def test_signal_callbacks_can_reenter_state_and_control_operations() -> None:
    """Run callbacks outside the lock so reentrant operations cannot deadlock."""
    signal = ControllableCancellationSignal()
    observations: list[tuple[bool, str | None]] = []
    unsubscribe_holder: list[Callable[[], None]] = []

    def callback(reason: str | None) -> None:
        """Observe committed state and invoke completed controls reentrantly."""
        # State is visible before delivery. Repeated cancel and unsubscribe are
        # no-ops because the transition snapshot already owns this callback.
        observations.append((signal.is_cancelled, signal.reason))
        signal.cancel("reentrant_reason")
        unsubscribe_holder[0]()
        assert reason == "outer_reason"

    unsubscribe_holder.append(signal.subscribe(callback))

    signal.cancel("outer_reason")

    assert observations == [(True, "outer_reason")]
    assert signal.reason == "outer_reason"


def test_signal_notifies_remaining_callbacks_before_reraising_first_failure() -> None:
    """Prevent one subscriber failure from hiding cancellation from another."""
    signal = ControllableCancellationSignal()
    failure = RuntimeError("subscriber failed")
    deliveries: list[str | None] = []

    def fail(reason: str | None) -> None:
        """Raise one exact configured callback failure."""
        # Accept the delivered reason before failing so order remains observable.
        assert reason == "test_reason"
        raise failure

    signal.subscribe(fail)
    signal.subscribe(deliveries.append)

    try:
        signal.cancel("test_reason")
    except RuntimeError as error:
        # Identity proves cancellation does not wrap or replace callback failure.
        assert error is failure
    else:
        raise AssertionError("Expected subscriber failure to be re-raised.")

    assert deliveries == ["test_reason"]
    assert signal.is_cancelled is True
    assert signal.reason == "test_reason"
    signal.cancel("ignored")
    assert deliveries == ["test_reason"]


def test_signal_first_concurrent_cancellation_wins_atomically() -> None:
    """Commit one reason and one delivery under simultaneous control calls."""
    signal = ControllableCancellationSignal()
    deliveries: list[str | None] = []
    signal.subscribe(deliveries.append)
    reasons = tuple(f"thread-{index}" for index in range(8))
    barrier = Barrier(len(reasons) + 1)

    def cancel_after_barrier(reason: str) -> None:
        """Release one competing cancellation with all worker threads."""
        # The barrier concentrates the race while the signal lock determines one
        # atomic winner without relying on thread start order.
        barrier.wait()
        signal.cancel(reason)

    threads = tuple(
        Thread(target=cancel_after_barrier, args=(reason,)) for reason in reasons
    )
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=2)

    # Every worker terminates, exactly one reason wins, and the callback observes
    # that same stable reason once despite concurrent requests.
    assert all(not thread.is_alive() for thread in threads)
    assert signal.reason in reasons
    assert deliveries == [signal.reason]
    assert signal.is_cancelled is True


def test_signal_instances_do_not_share_cancellation_state() -> None:
    """Keep independent interaction lifecycles completely isolated."""
    first = ControllableCancellationSignal()
    second = ControllableCancellationSignal()
    first_deliveries: list[str | None] = []
    second_deliveries: list[str | None] = []
    first.subscribe(first_deliveries.append)
    second.subscribe(second_deliveries.append)

    first.cancel("first_only")

    # Cancelling one signal changes neither state nor subscriptions in another.
    assert first.is_cancelled is True
    assert first_deliveries == ["first_only"]
    assert second.is_cancelled is False
    assert second.reason is None
    assert second_deliveries == []

    second.cancel("second_only")
    assert second_deliveries == ["second_only"]


def test_signal_rejects_invalid_inputs_without_mutating_state() -> None:
    """Reject non-callable subscribers and non-string reasons before transition."""
    signal = ControllableCancellationSignal()
    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: signal.subscribe(cast(Callable[[str | None], None], object())),
            "callback must be callable",
        ),
        (
            lambda: signal.cancel(cast(str | None, object())),
            "reason must be a string or None",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Stable diagnostics keep invalid fixture use distinct from an
            # intentional cancellation branch in the system under test.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid cancellation signal usage.")

    assert signal.is_cancelled is False
    assert signal.reason is None


def test_signal_has_exact_control_and_consumer_surface() -> None:
    """Expose protocol observation plus one explicit test-owned transition."""
    signal = ControllableCancellationSignal()
    is_cancelled = inspect.getattr_static(
        ControllableCancellationSignal, "is_cancelled"
    )
    reason = inspect.getattr_static(ControllableCancellationSignal, "reason")
    subscribe = ControllableCancellationSignal.subscribe
    cancel = ControllableCancellationSignal.cancel

    # Consumer members match CancellationSignal while cancel remains a simple
    # synchronous source operation owned only by this testing implementation.
    assert isinstance(is_cancelled, property)
    assert is_cancelled.fget is not None
    assert get_type_hints(is_cancelled.fget) == {"return": bool}
    assert isinstance(reason, property)
    assert reason.fget is not None
    assert get_type_hints(reason.fget) == {"return": str | None}
    assert tuple(inspect.signature(subscribe).parameters) == ("self", "callback")
    assert get_type_hints(subscribe) == {
        "callback": Callable[[str | None], None],
        "return": Callable[[], None],
    }
    assert tuple(inspect.signature(cancel).parameters) == ("self", "reason")
    assert get_type_hints(cancel) == {
        "reason": str | None,
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(subscribe)
    assert not inspect.iscoroutinefunction(cancel)

    # A completed lifecycle cannot be reset or replaced, and the signal does not
    # own tasks, deadlines, transport, or arbitrary trigger sequencing.
    for forbidden_member in (
        "reset",
        "set_reason",
        "uncancel",
        "trigger",
        "deadline",
        "task",
        "send",
    ):
        assert not hasattr(signal, forbidden_member)
