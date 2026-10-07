"""Recording configurable test double for interaction monitoring."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import ComponentDescriptor, MonitoringEvent


class StubInteractionMonitor:
    """Record lifecycle events and optionally raise one configured failure.

    The stub structurally implements ``InteractionMonitor`` without SDK
    inheritance. Its immutable ``observed_events`` declaration is fixed at
    construction, while every :meth:`on_event` call records the exact supplied
    ``MonitoringEvent`` before returning or raising the configured failure.
    Failed observations therefore remain visible to contract tests.

    Events and failures are retained by identity and never copied, transformed,
    redacted, wrapped, exported, or isolated. The ordered event record is exposed
    as a fresh immutable tuple so callers cannot mutate internal history.

    Filtering and failure isolation belong to the owning monitoring chain. This
    test double performs no request access, interaction control, logging,
    tracing, metrics export, or cross-component order recording. Configuration
    is fixed at construction; no reset or dynamic reconfiguration API exists.
    """

    __slots__ = ("_descriptor", "_error", "_events", "_observed_events")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        observed_events: frozenset[OpenIdentifier] | None,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Validate and retain metadata, subscription, and failure behavior.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            observed_events: Exact immutable event filter, or ``None`` for all.
            error: Optional exact failure raised after recording an event.

        Raises:
            TypeError: If metadata, the filter, its members, or the configured
                failure has an invalid nominal type.
        """
        descriptor_value = cast(object, descriptor)
        observed_events_value = cast(object, observed_events)
        error_value = cast(object, error)

        # Reject malformed fixture setup before a monitoring chain consumes an
        # invalid component declaration or publishes an event to this instance.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if observed_events_value is not None and not isinstance(
            observed_events_value, frozenset
        ):
            raise TypeError("observed_events must be a frozenset or None.")
        if isinstance(observed_events_value, frozenset):
            for event_type in cast(frozenset[object], observed_events_value):
                if not isinstance(event_type, OpenIdentifier):
                    raise TypeError(
                        "observed_events must contain OpenIdentifier values."
                    )
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")

        self._descriptor = descriptor
        self._observed_events = observed_events
        self._error = error
        self._events: list[MonitoringEvent] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after monitor selection or publication begins.
        return self._descriptor

    @property
    def observed_events(self) -> frozenset[OpenIdentifier] | None:
        """Return the exact configured immutable event filter or ``None``."""
        # Identity preservation lets tests distinguish the all-events declaration
        # from a specific, possibly empty, immutable subscription set.
        return self._observed_events

    @property
    def events(self) -> tuple[MonitoringEvent, ...]:
        """Return an immutable snapshot of events received in invocation order."""
        # A fresh tuple freezes current membership while preserving exact event
        # identities; later observations cannot alter an earlier snapshot.
        return tuple(self._events)

    async def on_event(self, event: MonitoringEvent) -> None:
        """Record one exact event, then return or raise the configured failure.

        Args:
            event: Immutable, already-redacted lifecycle event to observe.

        Raises:
            TypeError: If a dynamic caller supplies a non-MonitoringEvent value.
            BaseException: The exact configured monitoring failure, when present.
        """
        event_value = cast(object, event)
        if not isinstance(event_value, MonitoringEvent):
            raise TypeError("event must be a MonitoringEvent.")

        # Record before evaluating the configured outcome so a failed monitor
        # attempt remains observable without copying or changing the event.
        self._events.append(event)
        if self._error is not None:
            # Preserve failure identity, type, message, and control-flow class;
            # the owning monitoring chain decides whether and how to isolate it.
            raise self._error
