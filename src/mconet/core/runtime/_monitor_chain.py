"""Ordered publication of one monitoring event."""

from __future__ import annotations

from typing import cast

from mconet.core.spi.interaction_monitor import InteractionMonitor
from mconet.core.spi.monitoring_event import MonitoringEvent


async def publish_monitor_chain(
    monitors: tuple[InteractionMonitor, ...],
    event: MonitoringEvent,
) -> None:
    """Deliver one event to configured monitors in tuple order.

    A monitor is skipped when its filter does not include the event type.
    Skipping does not reorder the monitors that do receive the event. Every
    matching monitor receives the same event object. This stage does not
    isolate monitor failures.

    Args:
        monitors: Monitors in the order they were configured.
        event: The event to publish.

    Raises:
        TypeError: If an argument or a monitor has an invalid type.
        Exception: If a matching monitor fails while observing the event.
    """
    monitors_value = cast(object, monitors)
    event_value = cast(object, event)
    if not isinstance(monitors_value, tuple):
        raise TypeError("monitors must be a tuple.")
    if not isinstance(event_value, MonitoringEvent):
        raise TypeError("event must be a MonitoringEvent.")
    for monitor in cast(tuple[object, ...], monitors_value):
        if not isinstance(monitor, InteractionMonitor):
            raise TypeError("monitors must contain InteractionMonitor values.")
        observed = monitor.observed_events
        if observed is None or event_value.type in observed:
            await monitor.on_event(event_value)
