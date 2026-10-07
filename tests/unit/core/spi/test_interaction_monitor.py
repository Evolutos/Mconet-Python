"""Structural, privacy, and failure-isolation tests for interaction monitors."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import FrozenInstanceError
from typing import cast, get_type_hints

from mconet.core.domain import JsonValue, OpenIdentifier, Timestamp
from mconet.core.spi import ComponentDescriptor, InteractionMonitor, MonitoringEvent


class _RecordingMonitor:
    """Ordinary monitor recording exact events without modifying them."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        observed_events: frozenset[OpenIdentifier] | None,
    ) -> None:
        """Store metadata, immutable subscription, and an empty event record."""
        # The declared filter is fixed for the monitor instance while the event
        # list records invocation order without altering published event values.
        self.descriptor = descriptor
        self.observed_events = observed_events
        self.events: list[MonitoringEvent] = []

    async def on_event(self, event: MonitoringEvent) -> None:
        """Yield once and record the exact read-only event reference."""
        # A genuine awaitable boundary models asynchronous export without request
        # access, lifecycle control, event reconstruction, or network assumptions.
        await asyncio.sleep(0)
        self.events.append(event)


class _FailingMonitor:
    """Complete monitor raising one configured diagnostic failure."""

    descriptor = ComponentDescriptor("Failing monitor", "1.0.0", "application")
    """Valid metadata isolates event-observation failure behavior."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """Observe all events so filtering cannot hide the configured failure."""

    def __init__(self, failure: RuntimeError) -> None:
        """Store the exact error raised during asynchronous observation."""
        # Exception identity lets the chain diagnose the monitor without treating
        # its error as an interaction, protocol, authorization, or transport error.
        self.failure = failure

    async def on_event(self, event: MonitoringEvent) -> None:
        """Raise the configured failure without changing the supplied event."""
        # Accept the complete event before failing, but produce no mutation,
        # replacement event, cancellation, retry, or downstream control signal.
        del event
        raise self.failure


class _IncompleteMonitor:
    """Component-shaped fixture intentionally missing event observation."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates absence of the required callback."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """A valid filter cannot substitute for the missing callback."""


def _event() -> MonitoringEvent:
    """Build one complete privacy-bounded lifecycle event."""
    # Payload and metadata contain only non-sensitive JSON facts; request bodies,
    # credentials, authorization fields, and runtime objects remain absent.
    return MonitoringEvent(
        id="event-1",
        type=OpenIdentifier("integration.resolved"),
        interaction_id="interaction-1",
        trace_id="trace-1",
        timestamp=Timestamp(1_800_000_000, 123_456_789),
        payload={
            "source": "resolved_binding",
            "componentName": "Fixture adapter",
            "durationMilliseconds": 3,
        },
        metadata={"region": "test-region", "sampled": True},
    )


def _accept_monitor(monitor: InteractionMonitor) -> InteractionMonitor:
    """Return a monitor after crossing the statically checked protocol boundary."""
    # Pyright verifies ordinary structural behavior without SDK inheritance,
    # registry membership, a next callback, or one telemetry vendor API.
    return monitor


async def _publish_with_failure_isolation(
    monitor: InteractionMonitor,
    event: MonitoringEvent,
    interaction_result: object,
) -> object:
    """Model the chain boundary that isolates one monitor failure."""
    # The chain awaits observation for ordering but catches diagnostic failures;
    # it always returns the pre-existing main interaction result unchanged.
    try:
        await monitor.on_event(event)
    except Exception:
        pass
    return interaction_result


def test_interaction_monitor_accepts_structural_implementation() -> None:
    """Require only metadata, an immutable filter, and async observation."""
    monitor = _RecordingMonitor(
        ComponentDescriptor("Fixture monitor", "1.0.0", "application"),
        None,
    )

    accepted = _accept_monitor(monitor)

    # Static and runtime conformance agree without a base class or registration.
    assert accepted is monitor
    assert isinstance(monitor, InteractionMonitor)
    assert monitor.descriptor.name == "Fixture monitor"


def test_interaction_monitor_preserves_event_identity_and_read_only_state() -> None:
    """Observe the exact privacy-bounded event without changing its fields."""
    event = _event()
    monitor = _RecordingMonitor(
        ComponentDescriptor("Fixture monitor", "1.0.0", "application"),
        None,
    )
    original_state = (
        event.id,
        event.type,
        event.interaction_id,
        event.trace_id,
        event.timestamp,
        event.payload,
        dict(event.metadata),
    )

    result = asyncio.run(monitor.on_event(event))

    # Observation returns no control value, records the original object, and
    # leaves all correlation, payload, and metadata facts unchanged.
    assert result is None
    assert monitor.events == [event]
    assert monitor.events[0] is event
    assert (
        event.id,
        event.type,
        event.interaction_id,
        event.trace_id,
        event.timestamp,
        event.payload,
        dict(event.metadata),
    ) == original_state
    try:
        event.__setattr__("interaction_id", "replacement")
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Expected MonitoringEvent reassignment rejection.")


def test_interaction_monitor_preserves_optional_event_filter_semantics() -> None:
    """Distinguish all-event observation from an immutable selected set."""
    integration_event = OpenIdentifier("integration.resolved")
    failure_event = OpenIdentifier("interaction.failed")
    selected = frozenset((integration_event, failure_event))
    all_events = _RecordingMonitor(
        ComponentDescriptor("All events", "1.0.0", "application"),
        None,
    )
    filtered = _RecordingMonitor(
        ComponentDescriptor("Selected events", "1.0.0", "application"),
        selected,
    )

    # None is an explicit subscription to every type; a frozenset retains exact
    # open identifiers without allowing membership changes during interaction.
    assert all_events.observed_events is None
    assert filtered.observed_events is selected
    assert filtered.observed_events == frozenset(
        (OpenIdentifier("integration.resolved"), OpenIdentifier("interaction.failed"))
    )
    assert not hasattr(filtered.observed_events, "add")


def test_interaction_monitor_failure_does_not_replace_interaction_result() -> None:
    """Require the publishing boundary to isolate monitor-only failures."""
    failure = RuntimeError("telemetry backend unavailable")
    monitor = _FailingMonitor(failure)
    event = _event()
    interaction_result = object()

    result = asyncio.run(
        _publish_with_failure_isolation(monitor, event, interaction_result)
    )

    # The chain consumes the diagnostic failure and returns the exact pre-existing
    # interaction result; event identity and contents remain available unchanged.
    assert result is interaction_result
    assert event.id == "event-1"
    assert event.type == OpenIdentifier("integration.resolved")
    payload = cast(dict[str, JsonValue], event.payload)
    assert payload["source"] == "resolved_binding"


def test_interaction_monitor_exposes_exact_async_method_surface() -> None:
    """Lock filter type, event-only input, None result, and async semantics."""
    observed_events = inspect.getattr_static(InteractionMonitor, "observed_events")
    on_event = InteractionMonitor.on_event

    # The callback receives no request, authorization, credential, context,
    # next function, cancellation handle, or mutable interaction result.
    assert isinstance(observed_events, property)
    assert observed_events.fget is not None
    assert get_type_hints(observed_events.fget) == {
        "return": frozenset[OpenIdentifier] | None,
    }
    assert tuple(inspect.signature(on_event).parameters) == ("self", "event")
    assert get_type_hints(on_event) == {
        "event": MonitoringEvent,
        "return": type(None),
    }
    assert inspect.iscoroutinefunction(on_event)


def test_interaction_monitor_requires_complete_behavior_surface() -> None:
    """Reject metadata and filtering without asynchronous observation."""
    incomplete = _IncompleteMonitor()

    # Descriptor and subscription declarations cannot replace on_event.
    assert not isinstance(incomplete, InteractionMonitor)


def test_interaction_monitor_excludes_interception_and_execution_controls() -> None:
    """Keep request mutation, chain control, and execution stages out of monitors."""
    monitor = _RecordingMonitor(
        ComponentDescriptor("Fixture monitor", "1.0.0", "application"),
        None,
    )

    # Monitor implementations can export observations but cannot control chain
    # progression or access adjacent request-processing capabilities.
    for forbidden_member in (
        "next",
        "stop",
        "cancel",
        "modify_request",
        "normalize",
        "encode",
        "authorize",
        "send",
        "retry",
    ):
        assert not hasattr(monitor, forbidden_member)
