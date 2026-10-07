"""Reusable filter, privacy, read-only, and failure-isolation monitor assertions."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.domain import OpenIdentifier, Timestamp
from mconet.core.spi import (
    ComponentDescriptor,
    InteractionMonitor,
    MonitoringEvent,
)
from mconet.testing._json_value_snapshot import (
    JsonValueSnapshot,
    snapshot_json_value,
)
from mconet.testing.secret_scanner import SecretScanner

_ValueT = TypeVar("_ValueT")
_EventSnapshot = tuple[
    str,
    OpenIdentifier,
    str,
    str | None,
    Timestamp,
    JsonValueSnapshot,
    JsonValueSnapshot,
]
_EVENT_MUTATION_MESSAGE = "monitor must not mutate the monitoring event."


class MonitorContractSuite:
    """Apply filter, safe observation, and isolated-failure contracts.

    The suite is independent of pytest, unittest, telemetry vendors, fixture
    formats, and monitoring-chain implementations. Callers provide one known
    synthetic plaintext for privacy verification and inspect the exact immutable
    event or exact monitor failure through synchronous assertion callbacks.

    Construction validates one structural :class:`InteractionMonitor`, its
    immutable event filter, and asynchronous callback boundary. Every observation
    rechecks filter stability, requires the input to be a nominal
    :class:`MonitoringEvent`, scans the complete event for known plaintext, and
    snapshots all fields before invoking the monitor. Payload and metadata use a
    recursion-independent canonical JSON snapshot so nested mutation is detected.

    A successful observation must return ``None``. The isolated-failure case
    catches the monitor-only failure and exposes it to the assertion without
    propagating it as an interaction failure. Callback failures still propagate
    exactly. The suite performs no filtering decision, event construction,
    redaction, logging, export, chain traversal, request access, interaction
    cancellation, retry, authorization, transport, or network I/O.
    """

    __slots__ = ("_monitor", "_observed_events")

    def __init__(self, monitor: InteractionMonitor) -> None:
        """Validate and retain one structurally conforming async monitor.

        Args:
            monitor: Custom or SDK monitor subjected to reusable cases.

        Raises:
            TypeError: If the object, descriptor, filter, or callback violates
                the public monitor boundary.
        """
        monitor_value = cast(object, monitor)
        if not isinstance(monitor_value, InteractionMonitor):
            raise TypeError("monitor must implement InteractionMonitor.")
        descriptor_value = cast(object, monitor.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("monitor descriptor must be a ComponentDescriptor.")

        # Observation is the monitor's only asynchronous extension point. Reject
        # sync look-alikes before reading or retaining subscription state.
        on_event = monitor.on_event
        if not (
            iscoroutinefunction(on_event)
            or iscoroutinefunction(type(on_event).__call__)
        ):
            raise TypeError("monitor on_event operation must be asynchronous.")

        observed_events = _read_observed_events(monitor)
        self._monitor = monitor
        self._observed_events = observed_events

    def assert_observed_events(
        self,
        *,
        assertion: Callable[[frozenset[OpenIdentifier] | None], None],
    ) -> None:
        """Validate and expose the stable immutable event subscription.

        Args:
            assertion: Synchronous callback asserting all-events or selected
                event-filter facts.

        Raises:
            TypeError: If ``assertion`` or the current filter shape is invalid.
            AssertionError: If filter membership changed after construction.
            BaseException: Any exact assertion callback failure.
        """
        # Callback setup is checked before the monitor property is read again so
        # invalid contract code cannot be confused with filter instability.
        checked_assertion = _validate_assertion(assertion)
        current = _read_observed_events(self._monitor)
        _assert_filter_unchanged(current, self._observed_events)
        checked_assertion(current)

    async def assert_observe(
        self,
        event: MonitoringEvent,
        *,
        secret: str,
        assertion: Callable[[MonitoringEvent], None],
    ) -> None:
        """Validate one successful safe, read-only event observation.

        Args:
            event: Exact immutable monitoring event supplied to the monitor.
            secret: Exact non-empty synthetic plaintext that must be absent.
            assertion: Synchronous callback asserting exact observation facts.

        Raises:
            TypeError: If an input or ``assertion`` violates its public shape.
            AssertionError: If plaintext is present, the monitor mutates the
                event or filter, or observation returns a non-``None`` value.
            BaseException: Any exact monitor or assertion callback failure.
        """
        # Validate all test-owned setup and capture state before the only monitor
        # invocation so a bad case cannot be mistaken for monitor behavior.
        checked_assertion = _validate_assertion(assertion)
        checked_event = _validate_safe_event(event, secret)
        _assert_filter_stable(self._monitor, self._observed_events)
        snapshot = _snapshot_event(checked_event)

        result = await self._monitor.on_event(checked_event)
        _assert_event_unchanged(checked_event, snapshot)
        _assert_filter_stable(self._monitor, self._observed_events)
        if result is not None:
            raise AssertionError("monitor on_event must return None.")
        checked_assertion(checked_event)

    async def assert_failure_isolated(
        self,
        event: MonitoringEvent,
        *,
        secret: str,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require one monitor failure to remain an isolated diagnostic.

        Args:
            event: Exact immutable monitoring event supplied to the monitor.
            secret: Exact non-empty synthetic plaintext that must be absent.
            assertion: Synchronous callback asserting exact monitor failure facts.

        Raises:
            TypeError: If an input or ``assertion`` violates its public shape.
            AssertionError: If observation succeeds, mutates the event, or changes
                filter membership.
            asyncio.CancelledError: If this contract-case task is cancelled.
            BaseException: Any exact assertion callback failure.
        """
        # The same privacy and read-only snapshot applies before a monitor that
        # is expected to fail, preventing failure from hiding unsafe behavior.
        checked_assertion = _validate_assertion(assertion)
        checked_event = _validate_safe_event(event, secret)
        _assert_filter_stable(self._monitor, self._observed_events)
        snapshot = _snapshot_event(checked_event)

        try:
            # Catch BaseException deliberately so a configured diagnostic fixture
            # retains its exact type and identity at the isolation boundary.
            await self._monitor.on_event(checked_event)
        except asyncio.CancelledError as error:
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                # Cancellation of this assertion task is interaction control,
                # not a diagnostic failure produced by the monitor under test.
                raise
            captured_error = error
        except BaseException as error:
            captured_error = error
        else:
            _assert_event_unchanged(checked_event, snapshot)
            _assert_filter_stable(self._monitor, self._observed_events)
            raise AssertionError("monitor was expected to fail observation.")

        # State checks precede the callback so failure cannot hide mutation.
        # Running outside the catch block keeps callback errors distinguishable.
        _assert_event_unchanged(checked_event, snapshot)
        _assert_filter_stable(self._monitor, self._observed_events)
        checked_assertion(captured_error)


def _read_observed_events(
    monitor: InteractionMonitor,
) -> frozenset[OpenIdentifier] | None:
    """Read and validate one immutable event-filter declaration."""
    observed_events = cast(object, monitor.observed_events)
    if observed_events is None:
        return None
    if not isinstance(observed_events, frozenset):
        raise TypeError("monitor observed_events must be a frozenset or None.")
    for event_type in cast(frozenset[object], observed_events):
        if not isinstance(event_type, OpenIdentifier):
            raise TypeError(
                "monitor observed_events must contain OpenIdentifier values."
            )
    return cast(frozenset[OpenIdentifier], observed_events)


def _assert_filter_stable(
    monitor: InteractionMonitor,
    expected: frozenset[OpenIdentifier] | None,
) -> None:
    """Require subscription semantics to remain fixed across observation."""
    current = _read_observed_events(monitor)
    _assert_filter_unchanged(current, expected)


def _assert_filter_unchanged(
    current: frozenset[OpenIdentifier] | None,
    expected: frozenset[OpenIdentifier] | None,
) -> None:
    """Compare all-events or selected-event subscription semantics."""
    # None and an empty frozenset have different meanings, so both value and
    # optional-state equality are required rather than truthiness comparison.
    if current != expected or (current is None) != (expected is None):
        raise AssertionError("monitor observed_events must remain unchanged.")


def _validate_safe_event(event: MonitoringEvent, secret: str) -> MonitoringEvent:
    """Require one nominal event with no known synthetic plaintext."""
    event_value = cast(object, event)
    if not isinstance(event_value, MonitoringEvent):
        raise TypeError("event must be a MonitoringEvent.")

    # SecretScanner traverses the immutable dataclass and recursive JSON carriers
    # without stringifying caller objects or retaining the protected plaintext.
    SecretScanner().assert_absent(secret, event_value)
    return event_value


def _snapshot_event(event: MonitoringEvent) -> _EventSnapshot:
    """Capture every public event field without recursive Python calls."""
    # Metadata membership is already frozen at the top level, while nested JSON
    # values and payload containers still require complete structural snapshots.
    return (
        event.id,
        event.type,
        event.interaction_id,
        event.trace_id,
        event.timestamp,
        snapshot_json_value(event.payload),
        snapshot_json_value(dict(event.metadata)),
    )


def _assert_event_unchanged(
    event: MonitoringEvent,
    expected: _EventSnapshot,
) -> None:
    """Require complete event state to match its pre-observation snapshot."""
    try:
        current = _snapshot_event(event)
    except BaseException:
        # Malformed or unreadable post-call state is itself mutation. Use fixed
        # diagnostics without rendering event or payload data.
        raise AssertionError(_EVENT_MUTATION_MESSAGE) from None
    if current != expected:
        raise AssertionError(_EVENT_MUTATION_MESSAGE)


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous assertion before monitor observation."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # Async callbacks would leave their checks unexecuted after the monitor
        # completes and create an unawaited coroutine in this callback slot.
        raise TypeError("assertion must be synchronous.")
    return assertion
