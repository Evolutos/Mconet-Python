"""Contract for asynchronous read-only interaction observation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import OpenIdentifier
from mconet.core.spi.monitoring_event import MonitoringEvent
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class InteractionMonitor(RuntimeComponent, Protocol):
    """Observe selected immutable, redacted interaction lifecycle events.

    ``observed_events`` is ``None`` when the monitor accepts every event type;
    otherwise its immutable identifiers let the monitoring chain avoid invoking
    the monitor for unrelated events. Filtering never changes publication order
    among monitors that observe the same event.

    :meth:`on_event` receives only one prebuilt :class:`MonitoringEvent`. It must
    treat the event as read-only and must not access an authorization value,
    credential, mutable request, full body, raw stream chunk, or interaction
    control operation through this contract. A monitor observes; it does not
    intercept, modify, cancel, retry, authorize, encode, or send an interaction.

    Monitor failures are diagnostic failures. The owning monitoring chain must
    isolate them from the main interaction result and continue its configured
    publication order; the monitor itself has no ``next`` callback or control
    over downstream observers.
    """

    @property
    def observed_events(self) -> frozenset[OpenIdentifier] | None:
        """Return an immutable event filter, or ``None`` to observe every type."""
        # The chain reads this declaration before invocation; the monitor cannot
        # mutate subscription membership while an interaction is in progress.
        ...

    async def on_event(self, event: MonitoringEvent) -> None:
        """Observe one immutable, already-redacted lifecycle event."""
        # The awaitable boundary permits asynchronous logging, tracing, metrics,
        # or auditing while the return type exposes no interaction control value.
        ...
