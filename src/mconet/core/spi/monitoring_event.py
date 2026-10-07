"""Immutable, portable observations emitted during one model interaction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    OpenIdentifier,
    Timestamp,
    validate_json_value_numbers,
    validate_open_identifier,
)


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    """Record one read-only, JSON-compatible interaction observation.

    Event identity and correlation values are preserved exactly so monitoring
    backends can deduplicate and join observations without SDK normalization.
    The open event type accepts standard and provider-defined namespaces. The
    payload and metadata boundary admits portable JSON data only; request bodies,
    credentials, authorization values, raw bytes, and arbitrary runtime objects
    therefore cannot cross this structural contract directly.

    Producers remain responsible for selecting already-redacted payload facts.
    This value validates representation safety but cannot infer whether an
    otherwise ordinary string contains business-sensitive information.
    """

    id: str
    """Producer-assigned event identifier used for deduplication."""

    type: OpenIdentifier
    """Open standard or provider-defined event type."""

    interaction_id: str
    """Identifier of the interaction that emitted this event."""

    trace_id: str | None
    """Optional external trace correlation identifier."""

    timestamp: Timestamp
    """Portable UTC instant at which the observation was created."""

    payload: JsonValue
    """Event-specific, already-redacted JSON payload."""

    metadata: Extensions
    """Read-only portable metadata for monitoring backend correlation."""

    def __post_init__(self) -> None:
        """Validate the complete event and freeze metadata membership."""
        event_id = cast(object, self.id)
        event_type = cast(object, self.type)
        interaction_id = cast(object, self.interaction_id)
        trace_id = cast(object, self.trace_id)
        timestamp = cast(object, self.timestamp)

        # Correlation values are opaque producer-owned strings. This contract
        # verifies their primitive representation without imposing a UUID,
        # trace-provider format, or normalization that could break round trips.
        if not isinstance(event_id, str):
            raise TypeError("MonitoringEvent id must be a string.")
        if not isinstance(interaction_id, str):
            raise TypeError("MonitoringEvent interaction_id must be a string.")
        if trace_id is not None and not isinstance(trace_id, str):
            raise TypeError("MonitoringEvent trace_id must be a string or None.")

        # Event names are extensible but must obey the shared portable grammar,
        # which accepts future namespaces without a closed standard-event list.
        if not isinstance(event_type, OpenIdentifier):
            raise TypeError("MonitoringEvent type must be an OpenIdentifier.")
        validate_open_identifier(event_type)

        # A nominal timestamp prevents local datetime timezone state or reduced
        # precision from entering the language-neutral monitoring boundary.
        if not isinstance(timestamp, Timestamp):
            raise TypeError("MonitoringEvent timestamp must be a Timestamp.")

        # Payload validation rejects cycles, bytes, secret wrappers, arbitrary
        # objects, unsafe integers, and non-finite floats before publication.
        validate_json_value_numbers(self.payload)

        # Metadata receives the same recursive JSON checks and an independent
        # read-only top-level snapshot so later caller membership changes cannot
        # alter an event already handed to one or more monitors.
        object.__setattr__(self, "metadata", _snapshot_metadata(self.metadata))


def _snapshot_metadata(value: Extensions) -> Extensions:
    """Validate metadata and return a read-only top-level snapshot."""
    candidate = cast(object, value)
    # Accept custom Mapping implementations at the public boundary while
    # excluding sequences and other objects with no JSON object semantics.
    if not isinstance(candidate, Mapping):
        raise TypeError("MonitoringEvent metadata must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("MonitoringEvent metadata keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Validate values before copying membership so construction either succeeds
    # with a complete safe snapshot or fails without publishing a partial event.
    for item in typed_source.values():
        validate_json_value_numbers(item)
    return MappingProxyType(dict(typed_source))
