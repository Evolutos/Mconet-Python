"""Open structural contract tests for MessageRole implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue, MessageRole, OpenIdentifier

_STANDARD_ROLES = ("message.system", "message.user", "message.assistant")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for custom role defaults."""
    # Each role receives its own dictionary so tests never rely on mutable state
    # shared through a default value while exposing the read-only mapping type.
    return {}


@dataclass(frozen=True, slots=True)
class _Role:
    """Immutable custom role proving structural implementation without inheritance."""

    id: OpenIdentifier
    """Open standard or provider-defined role identifier."""

    semantic: str | None = None
    """Optional human-readable role meaning."""

    raw_value: str | None = None
    """Optional exact provider wire spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role data retained without interpretation."""


def _serialize_role(role: MessageRole) -> dict[str, JsonValue]:
    """Serialize one role into its language-neutral public field shape."""
    document: dict[str, JsonValue] = {"id": role.id.value}

    # Optional values are emitted only when present, while extension membership
    # is copied exactly without interpreting provider-defined keys or values.
    if role.semantic is not None:
        document["semantic"] = role.semantic
    if role.raw_value is not None:
        document["rawValue"] = role.raw_value
    if role.extensions:
        document["extensions"] = dict(role.extensions)
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded role field."""
    # Rejecting non-object extension data before construction avoids unsafe casts
    # and keeps the round-trip helper independent of host-language coercion.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded role field."""
    # Role identifiers and present descriptive fields must remain exact strings;
    # booleans, numbers, null, and containers are never converted to text.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_role(document: dict[str, JsonValue]) -> _Role:
    """Reconstruct one custom role from its language-neutral field shape."""
    semantic_value = document.get("semantic")
    raw_value = document.get("rawValue")

    # Omitted optional strings remain None. Present values pass through exact
    # string checks, and unknown extension JSON is retained as one mapping.
    return _Role(
        id=OpenIdentifier(_require_string(document.get("id"), "id")),
        semantic=(
            _require_string(semantic_value, "semantic")
            if semantic_value is not None
            else None
        ),
        raw_value=(
            _require_string(raw_value, "rawValue") if raw_value is not None else None
        ),
        extensions=(
            _require_object(document.get("extensions"), "extensions")
            if "extensions" in document
            else {}
        ),
    )


def test_message_role_accepts_standard_structural_implementations() -> None:
    """Verify system, user, and assistant roles share one open contract."""
    roles = tuple(_Role(OpenIdentifier(value)) for value in _STANDARD_ROLES)

    # Structural runtime checks do not require inheritance or a registry, and
    # every standard identifier remains exact and independently distinguishable.
    assert all(isinstance(role, MessageRole) for role in roles)
    assert tuple(role.id.value for role in roles) == _STANDARD_ROLES
    assert len({role.id for role in roles}) == len(_STANDARD_ROLES)


def test_message_role_preserves_unknown_role_fields() -> None:
    """Verify an unknown role retains identity, semantics, raw text, and extensions."""
    identifier = OpenIdentifier("vendor.moderator")
    extensions: Extensions = {
        "vendor.reviewScope": {
            "channels": ["safety", "quality"],
            "required": True,
        }
    }
    role = _Role(
        id=identifier,
        semantic="Reviews content before delivery.",
        raw_value="Moderator",
        extensions=extensions,
    )

    # Unknown identity is never replaced by a standard role or generic sentinel;
    # every optional producer field remains the exact supplied value/reference.
    assert isinstance(role, MessageRole)
    assert role.id is identifier
    assert role.id.value == "vendor.moderator"
    assert role.semantic == "Reviews content before delivery."
    assert role.raw_value == "Moderator"
    assert role.extensions is extensions


def test_message_role_round_trips_unknown_role_through_json() -> None:
    """Verify unknown role data survives ordinary language-neutral JSON encoding."""
    role = _Role(
        id=OpenIdentifier("vendor.moderator"),
        semantic="Reviews content before delivery.",
        raw_value="Moderator",
        extensions={
            "vendor.reviewScope": {
                "channels": ["safety", "quality"],
                "required": True,
            }
        },
    )

    # JSON encode/decode exercises the portable representation rather than only
    # comparing the original Python object and its shared nested references.
    encoded = json.dumps(_serialize_role(role), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_role(_require_object(decoded, "role"))

    assert restored == role
    assert _serialize_role(restored) == _serialize_role(role)


def test_message_role_requires_the_complete_structural_surface() -> None:
    """Verify missing semantic, raw, or extension fields do not satisfy the protocol."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteRole:
        """Intentionally expose only identity and omit optional-field properties."""

        id: OpenIdentifier
        """Role identity alone is insufficient for lossless unknown data."""

    incomplete = _IncompleteRole(OpenIdentifier("message.user"))

    # Optional values may be None, but their properties must exist so consumers
    # can read one stable shape without reflection or implementation type checks.
    assert not isinstance(incomplete, MessageRole)
    assert not isinstance(cast(object, OpenIdentifier("message.user")), MessageRole)
