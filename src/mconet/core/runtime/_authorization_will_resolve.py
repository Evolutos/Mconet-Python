"""Runtime publication of the authorization.will_resolve monitor event."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.timestamp import Timestamp
from mconet.core.spi.interaction_monitor import InteractionMonitor
from mconet.core.spi.monitoring_event import MonitoringEvent
from mconet.core.spi.transport_request import TransportRequest

_EVENT_TYPE = OpenIdentifier("authorization.will_resolve")


async def publish_authorization_will_resolve(
    *,
    event_id: str,
    interaction_id: str,
    snapshot: TransportRequest,
    monitors: tuple[InteractionMonitor, ...],
    timestamp: Timestamp,
) -> MonitoringEvent:
    """Publish one redacted event before authorization handler resolution.

    The payload keeps the method, URL text, media type, and header names. It
    does not include header values, body bytes, the authorization decision, or
    the request object. Each monitor receives that same frozen event and
    nothing else. A monitor whose filter omits this event type is not called.

    Args:
        event_id: Producer identifier stored on the event.
        interaction_id: Interaction that owns this publication.
        snapshot: Request view already safe to describe to monitors.
        monitors: Monitors configured for this interaction, in call order.
        timestamp: Instant recorded on the event. The clock is not read here.

    Returns:
        The one event delivered to every matching monitor.

    Raises:
        TypeError: If an argument or a monitor has an invalid runtime type.
    """
    event_id_value = cast(object, event_id)
    interaction_id_value = cast(object, interaction_id)
    snapshot_value = cast(object, snapshot)
    monitors_value = cast(object, monitors)
    timestamp_value = cast(object, timestamp)
    if not isinstance(event_id_value, str):
        raise TypeError("event_id must be a string.")
    if not isinstance(interaction_id_value, str):
        raise TypeError("interaction_id must be a string.")
    if not isinstance(snapshot_value, TransportRequest):
        raise TypeError("snapshot must be a TransportRequest.")
    if not isinstance(monitors_value, tuple):
        raise TypeError("monitors must be a tuple.")
    if not isinstance(timestamp_value, Timestamp):
        raise TypeError("timestamp must be a Timestamp.")

    event = MonitoringEvent(
        event_id_value,
        _EVENT_TYPE,
        interaction_id_value,
        None,
        timestamp_value,
        _redacted_payload(snapshot_value),
        {},
    )
    for monitor in cast(tuple[object, ...], monitors_value):
        # Filtering stays here so a monitor cannot opt into the request object
        # by declaring a broader subscription.
        if not isinstance(monitor, InteractionMonitor):
            raise TypeError("monitors must contain InteractionMonitor values.")
        if _observes(monitor, _EVENT_TYPE):
            await monitor.on_event(event)
    return event


def _redacted_payload(snapshot: TransportRequest) -> dict[str, JsonValue]:
    """Describe the request without values that can carry a credential."""
    media_type = snapshot.body.media_type
    # Names identify fields. Values and body octets stay on the transport
    # request, which is not handed to the monitor.
    return {
        "method": snapshot.method,
        "url": snapshot.url.value,
        "media_type": f"{media_type.type}/{media_type.subtype}",
        "header_names": [field.name for field in snapshot.headers.values],
    }


def _observes(monitor: InteractionMonitor, event_type: OpenIdentifier) -> bool:
    """Return whether this monitor's filter includes the event type."""
    observed = monitor.observed_events
    # None is the documented subscription for every event type. An explicit
    # set that omits this type receives nothing from this publication.
    return observed is None or event_type in observed
