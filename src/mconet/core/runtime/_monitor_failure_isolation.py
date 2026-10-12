"""Monitor publication that cannot replace an interaction result."""

from __future__ import annotations

from typing import TypeVar, cast

from mconet.core.spi.interaction_monitor import InteractionMonitor
from mconet.core.spi.monitoring_event import MonitoringEvent

_T = TypeVar("_T")


async def publish_isolated_monitor_chain(
    monitors: tuple[InteractionMonitor, ...],
    event: MonitoringEvent,
    result: _T,
) -> tuple[_T, tuple[BaseException, ...]]:
    """Deliver one event without letting a monitor replace the result.

    Matching monitors are called in tuple order. An ``Exception`` from a
    monitor is retained and publication continues. The interaction result is
    returned by identity. ``KeyboardInterrupt`` and ``SystemExit`` still
    propagate.

    Args:
        monitors: Monitors in the order they were configured.
        event: The event to publish.
        result: The interaction result that monitors must not replace.

    Returns:
        The same result and the monitor exceptions, in monitor order.

    Raises:
        TypeError: If an argument or a monitor has an invalid type.
        BaseException: If a monitor raises a non-Exception base exception.
    """
    monitors_value = cast(object, monitors)
    event_value = cast(object, event)
    if not isinstance(monitors_value, tuple):
        raise TypeError("monitors must be a tuple.")
    if not isinstance(event_value, MonitoringEvent):
        raise TypeError("event must be a MonitoringEvent.")
    failures: list[BaseException] = []
    for monitor in cast(tuple[object, ...], monitors_value):
        if not isinstance(monitor, InteractionMonitor):
            raise TypeError("monitors must contain InteractionMonitor values.")
        observed = monitor.observed_events
        if observed is not None and event_value.type not in observed:
            continue
        try:
            await monitor.on_event(event_value)
        except Exception as error:
            failures.append(error)
    return result, tuple(failures)
