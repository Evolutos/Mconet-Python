"""Identity, opacity, and portability tests for ProtocolState."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import JsonValue, OpenIdentifier, ProtocolState


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Checking both class and text proves validation fails at the intended state
    # field instead of passing through an unrelated JSON or dataclass exception.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _serialize_state(state: ProtocolState) -> dict[str, JsonValue]:
    """Serialize one protocol state using its language-neutral field shape."""
    # Keep every identity as a separate string and pass the opaque JSON value
    # unchanged, without flattening it into protocol- or service-specific fields.
    return {
        "serviceId": state.service_id.value,
        "protocolId": state.protocol_id.value,
        "stateType": state.state_type.value,
        "stateValue": state.state_value,
    }


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required JSON object without coercing another value kind."""
    # The portable representation is named rather than positional, so scalars
    # and arrays cannot acquire ambiguous identity or state-field meanings.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without host-language conversion."""
    # Null, booleans, numbers, arrays, and objects cannot be stringified into an
    # identity the service did not actually report.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_state(document: dict[str, JsonValue]) -> ProtocolState:
    """Reconstruct one protocol state from its exact public JSON field shape."""
    if "stateValue" not in document:
        # Membership distinguishes a required JSON null from a missing state
        # value; neither the decoder nor constructor is allowed to invent it.
        raise AssertionError("stateValue must be present.")
    # Fresh identifiers prove reconstruction needs no service, protocol, or state-
    # type registry and preserves future namespaces through the same public path.
    return ProtocolState(
        service_id=OpenIdentifier(
            _require_string(document.get("serviceId"), "serviceId")
        ),
        protocol_id=OpenIdentifier(
            _require_string(document.get("protocolId"), "protocolId")
        ),
        state_type=OpenIdentifier(
            _require_string(document.get("stateType"), "stateType")
        ),
        state_value=document["stateValue"],
    )


def _state(state_value: JsonValue = None) -> ProtocolState:
    """Create one complete state with caller-selected opaque JSON data."""
    # Stable fixture identities let individual tests vary only state_value while
    # retaining a valid service, protocol, and open state classification.
    return ProtocolState(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        OpenIdentifier("state.conversation_cursor"),
        state_value,
    )


def test_protocol_state_keeps_all_dimensions_separate() -> None:
    """Verify service, protocol, state type, and value retain distinct ownership."""
    service_id = OpenIdentifier("service.vendor")
    protocol_id = OpenIdentifier("protocol.vendor")
    state_type = OpenIdentifier("state.conversation_cursor")
    state_value: JsonValue = {"cursor": "next-17", "expires": False}
    state = ProtocolState(service_id, protocol_id, state_type, state_value)

    # Identity checks prove the record neither derives identifiers from one
    # another nor rebuilds or interprets the integration-owned JSON value.
    assert state.service_id is service_id
    assert state.protocol_id is protocol_id
    assert state.state_type is state_type
    assert state.state_value is state_value


def test_protocol_state_preserves_unknown_state_through_json() -> None:
    """Verify future state types and nested values survive a real JSON round trip."""
    state = ProtocolState(
        OpenIdentifier("service.future"),
        OpenIdentifier("protocol.future"),
        OpenIdentifier("vendor.resume_checkpoint"),
        {"cursor": "opaque", "parts": [1, True, None]},
    )

    # Actual encoding and decoding demonstrate cross-process fidelity without a
    # known state registry or service-specific Core interpretation.
    encoded = json.dumps(_serialize_state(state), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_state(_require_object(decoded, "state"))

    assert restored == state
    assert restored.service_id is not state.service_id
    assert restored.protocol_id is not state.protocol_id
    assert restored.state_type is not state.state_type


def test_protocol_state_distinguishes_required_null_from_missing_state() -> None:
    """Verify JSON null is a valid explicit value while field omission is not."""
    state = _state(None)
    serialized = _serialize_state(state)

    # The required key remains present with None; removing it makes decoding fail
    # rather than silently fabricating a protocol state value.
    assert state.state_value is None
    assert "stateValue" in serialized
    assert serialized["stateValue"] is None
    del serialized["stateValue"]
    _assert_raises(
        AssertionError,
        lambda: _deserialize_state(serialized),
        "stateValue must be present",
    )


def test_protocol_state_has_frozen_complete_field_semantics() -> None:
    """Verify equality, field ownership, and assignment immutability are complete."""
    first = _state("cursor-a")
    same = _state("cursor-a")
    different = _state("cursor-b")

    # All four fields participate in value equality, while frozen outer storage
    # prevents a parsed response from replacing any identity or state value.
    assert first == same
    assert first != different
    assert tuple(field.name for field in fields(ProtocolState)) == (
        "service_id",
        "protocol_id",
        "state_type",
        "state_value",
    )
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("state_value", "changed"),
        "cannot assign to field",
    )


def test_protocol_state_contains_no_access_or_runtime_fields() -> None:
    """Verify opaque response state does not absorb credentials or control data."""
    state = _state({"cursor": "opaque"})

    # State carries returned protocol facts only; authorization, endpoint, task,
    # retry, polling, and runtime diagnostic ownership remain elsewhere.
    assert not hasattr(state, "authorization")
    assert not hasattr(state, "endpoint")
    assert not hasattr(state, "task")
    assert not hasattr(state, "retry_after")
    assert not hasattr(state, "polling_interval")
    assert not hasattr(state, "diagnostics")


def test_protocol_state_requires_nominal_identifier_fields() -> None:
    """Verify bare strings cannot substitute for any identity dimension."""
    valid = OpenIdentifier("identity.valid")
    invalid_cases = (
        (
            lambda: ProtocolState(cast(OpenIdentifier, "service"), valid, valid, None),
            "service_id",
        ),
        (
            lambda: ProtocolState(valid, cast(OpenIdentifier, "protocol"), valid, None),
            "protocol_id",
        ),
        (
            lambda: ProtocolState(valid, valid, cast(OpenIdentifier, "state"), None),
            "state_type",
        ),
    )

    # Exercise all three positions independently so field order cannot allow one
    # correct identifier to mask another dimension's invalid representation.
    for create_state, field_name in invalid_cases:
        _assert_raises(
            TypeError,
            create_state,
            f"{field_name} must be an OpenIdentifier",
        )


def test_protocol_state_validates_every_identifier_syntax() -> None:
    """Verify all identity dimensions obey the shared portable open grammar."""
    valid = OpenIdentifier("identity.valid")
    invalid_cases = (
        (lambda: ProtocolState(OpenIdentifier(""), valid, valid, None), "empty"),
        (
            lambda: ProtocolState(
                valid, OpenIdentifier("Protocol.Invalid"), valid, None
            ),
            "lowercase",
        ),
        (
            lambda: ProtocolState(valid, valid, OpenIdentifier("state invalid"), None),
            "whitespace",
        ),
    )

    # The common validator reports syntax without closing any of the three open
    # namespaces to currently known services, protocols, or state types.
    for create_state, message in invalid_cases:
        _assert_raises(ValueError, create_state, message)


def test_protocol_state_rejects_nonportable_state_values() -> None:
    """Verify opaque state still satisfies recursive JSON and number contracts."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    invalid_cases = (
        (cast(JsonValue, object()), TypeError, "structurally valid JsonValue"),
        (cast(JsonValue, ("tuple",)), TypeError, "structurally valid JsonValue"),
        (cast(JsonValue, {1: "value"}), TypeError, "structurally valid JsonValue"),
        (cyclic, TypeError, "structurally valid JsonValue"),
        (2**53, ValueError, "interoperable safe range"),
        (math.inf, ValueError, "must be finite"),
    )

    # Opaqueness prevents semantic interpretation, not structural or numeric
    # corruption of a value that must cross JSON-based platform boundaries.
    for state_value, error_type, message in invalid_cases:
        _assert_raises(
            error_type,
            lambda state_value=state_value: _state(state_value),
            message,
        )
