"""Open structural contract tests for MessageContentKind implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import JsonValue, MessageContentKind, OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Kind:
    """Immutable custom content kind proving inheritance-free implementation."""

    id: OpenIdentifier
    """Standard or provider-defined content representation identifier."""


def _serialize_kind(kind: MessageContentKind) -> dict[str, JsonValue]:
    """Serialize one content kind into its language-neutral public shape."""
    # The protocol owns identity only, so serialization never invents element
    # category, composition, content payload, metadata, or extension fields.
    return {"id": kind.id.value}


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded kind document."""
    # A named object prevents scalar and positional representations from becoming
    # incompatible language-specific alternatives to the public ID field.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded kind field."""
    # Exact string decoding avoids host-language conversion of null, booleans,
    # numbers, or containers into accidental identifiers.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_kind(document: dict[str, JsonValue]) -> _Kind:
    """Reconstruct one custom content kind from its public JSON shape."""
    # Reconstruction uses a new OpenIdentifier and performs no known-kind lookup,
    # preserving future namespaces exactly for later content implementations.
    return _Kind(OpenIdentifier(_require_string(document.get("id"), "id")))


def test_message_content_kind_expresses_text_kind() -> None:
    """Verify the initial text representation satisfies the open contract."""
    kind = _Kind(OpenIdentifier("content.text"))

    # Structural recognition requires no inheritance or registration, and the
    # identifier remains the exact standard value supplied by the producer.
    assert isinstance(kind, MessageContentKind)
    assert kind.id.value == "content.text"
    assert _serialize_kind(kind) == {"id": "content.text"}


def test_message_content_kind_preserves_unknown_kind_through_json() -> None:
    """Verify a provider-defined content identity survives a full JSON round trip."""
    kind = _Kind(OpenIdentifier("vendor.rich_text"))

    # Real JSON encoding and reconstruction prove fidelity is not an artifact of
    # comparing one Python object or reusing its identifier reference.
    encoded = json.dumps(_serialize_kind(kind), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_kind(_require_object(decoded, "kind"))

    assert isinstance(restored, MessageContentKind)
    assert restored == kind
    assert restored.id is not kind.id
    assert restored.id.value == "vendor.rich_text"


def test_message_content_kind_requires_identifier_surface() -> None:
    """Verify arbitrary content payload objects do not satisfy the kind protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingId:
        """Intentionally carry payload text without content-kind identity."""

        text: str
        """Payload data that cannot substitute for representation identity."""

    candidate = _MissingId("content")

    # Kind recognition depends only on the required ID property; neither payload
    # resemblance nor a bare OpenIdentifier is a complete structural kind object.
    assert not isinstance(candidate, MessageContentKind)
    assert not isinstance(
        cast(object, OpenIdentifier("content.text")), MessageContentKind
    )
