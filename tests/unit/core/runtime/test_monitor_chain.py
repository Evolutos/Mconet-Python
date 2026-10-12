"""Tests that monitors receive one event in configured order."""

from __future__ import annotations

import asyncio

from mconet.core.domain import OpenIdentifier, Timestamp
from mconet.core.runtime._monitor_chain import publish_monitor_chain
from mconet.core.spi import ComponentDescriptor, MonitoringEvent


class _Monitor:
    """Record this monitor's name when it observes an event."""

    def __init__(
        self,
        name: str,
        observed_events: frozenset[OpenIdentifier] | None,
        log: list[str],
    ) -> None:
        """Store the filter and the shared call log."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application")
        self.observed_events = observed_events
        self._log = log
        self._name = name
        self.events: list[MonitoringEvent] = []

    async def on_event(self, event: MonitoringEvent) -> None:
        """Append this monitor after earlier configured monitors."""
        self._log.append(self._name)
        self.events.append(event)


def test_monitors_are_called_in_configured_order() -> None:
    """Verify filters skip a monitor without reordering the others."""
    event_type = OpenIdentifier("interaction.completed")
    event = MonitoringEvent(
        "event-1",
        event_type,
        "interaction-1",
        None,
        Timestamp(1_700_000_000, 0),
        {"status": "completed"},
        {},
    )
    log: list[str] = []
    first = _Monitor("first", frozenset((event_type,)), log)
    skipped = _Monitor("skipped", frozenset((OpenIdentifier("other.event"),)), log)
    third = _Monitor("third", None, log)

    asyncio.run(publish_monitor_chain((first, skipped, third), event))

    assert log == ["first", "third"]
    assert first.events == [event]
    assert skipped.events == []
    assert third.events == [event]
