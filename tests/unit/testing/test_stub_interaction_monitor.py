"""Event recording and failure tests for StubInteractionMonitor."""

from __future__ import annotations

import asyncio
import inspect
from typing import cast, get_type_hints

from mconet.core.domain import OpenIdentifier, Timestamp
from mconet.core.spi import (
    ComponentDescriptor,
    InteractionMonitor,
    MonitoringEvent,
)
from mconet.testing import StubInteractionMonitor


def _event(event_id: str, event_type: str) -> MonitoringEvent:
    """Build one complete immutable and privacy-bounded lifecycle event."""
    # Distinct identifiers make event identity and invocation ordering observable
    # without introducing request bodies, credentials, or runtime-only objects.
    return MonitoringEvent(
        id=event_id,
        type=OpenIdentifier(event_type),
        interaction_id="interaction-1",
        trace_id="trace-1",
        timestamp=Timestamp(1_800_000_000, 123_456_789),
        payload={"state": "observed"},
        metadata={"region": "test-region"},
    )


def _stub(
    observed_events: frozenset[OpenIdentifier] | None = None,
    *,
    error: BaseException | None = None,
) -> StubInteractionMonitor:
    """Create one valid monitor Stub with deterministic configuration."""
    # Centralized metadata keeps each test focused on subscription, recording,
    # or failure behavior rather than repeating component construction details.
    return StubInteractionMonitor(
        ComponentDescriptor("Stub monitor", "1", "application"),
        observed_events,
        error=error,
    )


def _observe(stub: StubInteractionMonitor, event: MonitoringEvent) -> None:
    """Run one asynchronous event observation to completion."""
    # asyncio.run supplies an isolated event loop without background tasks,
    # scheduling assumptions, external exporters, or additional side effects.
    asyncio.run(stub.on_event(event))


def test_stub_structurally_implements_interaction_monitor() -> None:
    """Expose metadata, filtering, and async observation without inheritance."""
    stub = _stub()

    accepted: InteractionMonitor = stub

    # Static and runtime protocol checks recognize the ordinary object without a
    # registry, monitor base class, publication chain, or telemetry dependency.
    assert accepted is stub
    assert isinstance(stub, InteractionMonitor)
    assert stub.descriptor.name == "Stub monitor"


def test_stub_returns_exact_configured_event_filter() -> None:
    """Preserve all-events and selected-event subscription semantics."""
    selected = frozenset(
        (OpenIdentifier("integration.resolved"), OpenIdentifier("interaction.failed"))
    )
    all_events = _stub()
    filtered = _stub(selected)

    # None means every type, while identity preservation proves the Stub neither
    # copies, expands, normalizes, nor evaluates a selected immutable filter.
    assert all_events.observed_events is None
    assert filtered.observed_events is selected
    assert not hasattr(filtered.observed_events, "add")


def test_stub_records_exact_events_in_invocation_order() -> None:
    """Retain successful event identities and order without transformation."""
    stub = _stub()
    first = _event("event-1", "integration.resolved")
    second = _event("event-2", "interaction.completed")

    _observe(stub, first)
    first_snapshot = stub.events
    _observe(stub, second)

    # Fresh tuple snapshots protect internal membership, earlier views remain
    # time-bounded, and the event objects themselves are retained by identity.
    assert first_snapshot == (first,)
    assert stub.events == (first, second)
    assert stub.events[0] is first
    assert stub.events[1] is second
    assert not hasattr(stub.events, "append")


def test_stub_records_event_before_raising_exact_failure() -> None:
    """Keep a failed observation visible and preserve exception identity."""
    failure = RuntimeError("monitor exporter unavailable")
    stub = _stub(error=failure)
    event = _event("event-1", "interaction.failed")

    try:
        _observe(stub, event)
    except RuntimeError as error:
        # Identity proves the Stub does not wrap, translate, or isolate a failure
        # that belongs to the monitoring chain's publication boundary.
        assert error is failure
    else:
        raise AssertionError("Expected configured monitoring failure.")

    assert stub.events == (event,)
    assert stub.events[0] is event


def test_stub_validates_configuration_and_dynamic_event_boundary() -> None:
    """Reject malformed construction and non-event callback values."""
    descriptor = ComponentDescriptor("Stub monitor", "1", "application")
    invalid_calls = (
        (
            lambda: StubInteractionMonitor(
                cast(ComponentDescriptor, object()),
                None,
            ),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubInteractionMonitor(
                descriptor,
                cast(frozenset[OpenIdentifier] | None, set()),
            ),
            "observed_events must be a frozenset or None",
        ),
        (
            lambda: StubInteractionMonitor(
                descriptor,
                cast(frozenset[OpenIdentifier] | None, frozenset((1,))),
            ),
            "observed_events must contain OpenIdentifier values",
        ),
        (
            lambda: StubInteractionMonitor(
                descriptor,
                None,
                error=cast(BaseException, "failure"),
            ),
            "error must be a BaseException or None",
        ),
        (
            lambda: asyncio.run(_stub().on_event(cast(MonitoringEvent, object()))),
            "event must be a MonitoringEvent",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Stable diagnostics distinguish invalid Stub use from the exact
            # configured monitoring failure exercised by fault-injection tests.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub usage to fail.")


def test_stub_matches_monitor_surface_without_adjacent_responsibilities() -> None:
    """Expose the exact monitor contract plus required local event records."""
    stub = _stub()
    observed_events = inspect.getattr_static(StubInteractionMonitor, "observed_events")
    on_event = StubInteractionMonitor.on_event

    # The filter remains a property and observation retains the event-only async
    # signature defined by the SPI contract.
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

    # Event history is the sole local testing extension. Chain filtering,
    # reconfiguration, export, request access, and interaction control stay out.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "filter",
        "publish",
        "export",
        "request",
        "next",
        "cancel",
        "send",
    ):
        assert not hasattr(stub, forbidden_member)
