"""Open structural contract tests for InteractionMode implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from typing import cast

from mconet.core.domain import InteractionMode, JsonValue, OpenIdentifier

_STANDARD_MODES = (
    "unary",
    "server_stream",
    "client_stream",
    "duplex",
    "long_running",
)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Provide an immutable application-owned interaction mode value."""

    id: OpenIdentifier
    """Standard or provider-defined execution mode identity."""


def _accept_interaction_mode(mode: InteractionMode) -> InteractionMode:
    """Return one mode after crossing the static protocol boundary."""
    # Pyright verifies the caller exposes the exact nominal ID type, while the
    # runtime-checkable Protocol independently verifies attribute presence.
    return mode


def _serialize_mode(mode: InteractionMode) -> dict[str, JsonValue]:
    """Serialize one mode into its language-neutral public field shape."""
    # InteractionMode owns identity only, so serialization never invents task,
    # transport, lifecycle, capability, or support-policy fields.
    return {"id": mode.id.value}


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded mode document."""
    # A named object prevents scalar and positional forms from becoming alternate
    # platform-specific representations of the single public ID property.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without implicit conversion."""
    # Null, numbers, booleans, arrays, and objects cannot acquire accidental mode
    # identities through host-language string conversion.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_mode(document: dict[str, JsonValue]) -> _Mode:
    """Reconstruct one custom mode from its language-neutral field shape."""
    # Reconstruction creates a fresh open identifier and performs no known-mode
    # lookup, runtime capability decision, or client entry-point selection.
    return _Mode(OpenIdentifier(_require_string(document.get("id"), "id")))


def test_interaction_mode_expresses_all_standard_identifiers() -> None:
    """Verify unary and reserved future lifecycles share the open contract."""
    modes = tuple(_Mode(OpenIdentifier(value)) for value in _STANDARD_MODES)

    # Structural recognition neither requires SDK inheritance nor makes non-unary
    # modes executable; every documented identity remains exact and distinct.
    assert all(isinstance(mode, InteractionMode) for mode in modes)
    assert all(_accept_interaction_mode(mode) is mode for mode in modes)
    assert tuple(mode.id.value for mode in modes) == _STANDARD_MODES
    assert len({mode.id for mode in modes}) == len(_STANDARD_MODES)


def test_interaction_mode_preserves_unknown_value_through_json() -> None:
    """Verify a provider-defined future mode survives a complete JSON round trip."""
    mode = _Mode(OpenIdentifier("vendor.deferred_batch"))

    # Real JSON encode/decode proves preservation does not depend on Python object
    # identity, a closed enum, or reuse of the original OpenIdentifier instance.
    encoded = json.dumps(_serialize_mode(mode), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_mode(_require_object(decoded, "mode"))

    assert isinstance(restored, InteractionMode)
    assert restored == mode
    assert restored.id is not mode.id
    assert restored.id.value == "vendor.deferred_batch"


def test_interaction_mode_contains_only_execution_identity() -> None:
    """Verify mode values do not absorb task or runtime configuration fields."""
    mode = _Mode(OpenIdentifier("unary"))

    # The test implementation mirrors the one-property public protocol, proving
    # task type, transport, stream direction, and support flags are not required.
    assert tuple(field.name for field in fields(_Mode)) == ("id",)
    assert _serialize_mode(mode) == {"id": "unary"}
    assert not hasattr(mode, "task_type")
    assert not hasattr(mode, "transport")
    assert not hasattr(mode, "supported")


def test_interaction_mode_requires_identifier_surface() -> None:
    """Verify arbitrary execution data does not satisfy the mode protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingId:
        """Intentionally carry a lifecycle label without mode identity."""

        lifecycle: str
        """Text that cannot substitute for the required open identifier."""

    candidate = _MissingId("unary")

    # Recognition requires the ID property on a structural implementation; a
    # lifecycle-like object and a bare OpenIdentifier are both incomplete modes.
    assert not isinstance(candidate, InteractionMode)
    assert not isinstance(cast(object, OpenIdentifier("unary")), InteractionMode)
