"""Tests for portable, privacy-bounded monitoring event values."""

from __future__ import annotations

import math
import operator
from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import JsonValue, OpenIdentifier, SecretValue, Timestamp
from mconet.core.spi import MonitoringEvent


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str = "",
) -> None:
    """Require an action to raise one expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Optional message matching keeps field-boundary failures attributable
        # while allowing shared JSON validators to own their exact diagnostics.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _event(**changes: object) -> MonitoringEvent:
    """Build one complete event while allowing focused field replacements."""
    # Keeping the canonical valid fixture in one place makes each negative test
    # change only the boundary it intends to exercise.
    values: dict[str, object] = {
        "id": "event-42",
        "type": OpenIdentifier("interaction.started"),
        "interaction_id": "interaction-7",
        "trace_id": "trace-9",
        "timestamp": Timestamp(1_800_000_000, 123_456_789),
        "payload": {"serviceId": "openai", "attempt": 1},
        "metadata": {"region": "ap-east", "sampled": True},
    }
    values.update(changes)
    # The helper deliberately accepts object replacements so runtime validation
    # cases can cross the typed constructor boundary without suppressing checks.
    return MonitoringEvent(
        id=cast(str, values["id"]),
        type=cast(OpenIdentifier, values["type"]),
        interaction_id=cast(str, values["interaction_id"]),
        trace_id=cast(str | None, values["trace_id"]),
        timestamp=cast(Timestamp, values["timestamp"]),
        payload=cast(JsonValue, values["payload"]),
        metadata=cast(dict[str, JsonValue], values["metadata"]),
    )


def test_monitoring_event_preserves_complete_contract() -> None:
    """Preserve every detailed architecture field without normalization."""
    event = _event()

    # Exact field order keeps serializers and cross-language schema mapping
    # aligned with the complete monitoring contract, including trace correlation.
    assert tuple(field.name for field in fields(event)) == (
        "id",
        "type",
        "interaction_id",
        "trace_id",
        "timestamp",
        "payload",
        "metadata",
    )
    assert event.id == "event-42"
    assert event.type == OpenIdentifier("interaction.started")
    assert event.interaction_id == "interaction-7"
    assert event.trace_id == "trace-9"
    assert event.timestamp == Timestamp(1_800_000_000, 123_456_789)
    assert event.payload == {"serviceId": "openai", "attempt": 1}
    assert dict(event.metadata) == {"region": "ap-east", "sampled": True}


def test_monitoring_event_accepts_absent_trace_and_unknown_event_type() -> None:
    """Keep tracing optional and event namespaces forward-compatible."""
    event = _event(
        type=OpenIdentifier("vendor.pipeline.checkpoint"),
        trace_id=None,
    )

    # No known-event enumeration is consulted, so a portable future name is
    # preserved exactly while applications without tracing can use None.
    assert event.type.value == "vendor.pipeline.checkpoint"
    assert event.trace_id is None


def test_monitoring_event_is_value_comparable_and_outer_immutable() -> None:
    """Provide stable equality while rejecting field reassignment."""
    first = _event()
    second = _event()

    # Frozen dataclass semantics make complete event values comparable and stop
    # monitors from rewriting correlation facts after publication.
    assert first == second
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", "replacement"),
        "cannot assign to field",
    )


def test_monitoring_event_snapshots_metadata_membership() -> None:
    """Detach metadata keys from caller mutation and expose no write API."""
    metadata: dict[str, JsonValue] = {"region": "ap-east"}
    event = _event(metadata=metadata)
    metadata["late"] = True

    # Caller dictionary changes cannot retroactively alter the published event;
    # direct mutation is also rejected by the mapping proxy.
    assert dict(event.metadata) == {"region": "ap-east"}
    _assert_raises(
        TypeError,
        lambda: operator.setitem(
            cast(MutableMapping[str, JsonValue], event.metadata),
            "late",
            True,
        ),
        "does not support item assignment",
    )


def test_monitoring_event_rejects_invalid_nominal_fields() -> None:
    """Reject each malformed scalar or nominal value at its own boundary."""
    invalid_values = (
        ("id", 7, "id must be a string"),
        ("type", "interaction.started", "type must be an OpenIdentifier"),
        ("interaction_id", object(), "interaction_id must be a string"),
        ("trace_id", 9, "trace_id must be a string or None"),
        ("timestamp", "2027-01-15T08:00:00Z", "timestamp must be a Timestamp"),
    )

    # Focused replacement verifies errors are attributable to the named field
    # rather than deferred until a monitor attempts serialization.
    for field_name, invalid, message in invalid_values:
        _assert_raises(
            TypeError,
            lambda field_name=field_name, invalid=invalid: _event(
                **{field_name: invalid}
            ),
            message,
        )


def test_monitoring_event_validates_open_event_type() -> None:
    """Reject non-portable event names without closing the value set."""
    invalid_types = (
        OpenIdentifier("Interaction.Started"),
        OpenIdentifier("interaction..started"),
        OpenIdentifier(" interaction.started"),
    )

    # Shared grammar validation keeps event names interoperable across language
    # implementations while still accepting unknown valid namespaces.
    for invalid_type in invalid_types:
        _assert_raises(
            ValueError,
            lambda invalid_type=invalid_type: _event(type=invalid_type),
        )


def test_monitoring_event_rejects_unsafe_payload_values() -> None:
    """Prevent non-JSON, secret-wrapper, and non-portable numeric payloads."""
    invalid_payloads = (
        b"raw-response",
        SecretValue("credential"),
        object(),
        2**53,
        math.inf,
    )

    # Structural and number validation runs before the event can be published,
    # closing direct channels for credentials, raw bytes, and invalid JSON.
    for invalid_payload in invalid_payloads:
        try:
            _event(payload=invalid_payload)
        except (TypeError, ValueError):
            continue
        raise AssertionError("Expected invalid monitoring payload to be rejected.")


def test_monitoring_event_rejects_cyclic_payload() -> None:
    """Reject recursive containers that cannot be serialized as JSON."""
    payload: list[JsonValue] = []
    payload.append(payload)

    # Iterative cycle detection prevents recursion failure and returns one stable
    # boundary error before any monitor observes the malformed payload.
    _assert_raises(
        TypeError,
        lambda: _event(payload=payload),
        "structurally valid JsonValue",
    )


def test_monitoring_event_rejects_invalid_or_sensitive_metadata() -> None:
    """Require string-keyed portable JSON metadata without opaque values."""
    invalid_metadata = (
        [("region", "ap-east")],
        {1: "non-string-key"},
        {"raw": b"response"},
        {"secret": SecretValue("credential")},
        {"latency": math.nan},
        {"sequence": [1, object()]},
    )

    # Metadata cannot serve as an escape hatch around the payload's serialization
    # and privacy boundary, regardless of nesting depth.
    for metadata in invalid_metadata:
        try:
            _event(metadata=metadata)
        except (TypeError, ValueError):
            continue
        raise AssertionError("Expected invalid monitoring metadata to be rejected.")
