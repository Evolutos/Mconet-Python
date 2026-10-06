"""Open structural contract tests for ArtifactKind implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import ArtifactKind, Extensions, JsonValue, OpenIdentifier

_STANDARD_KINDS = (
    "artifact.text",
    "artifact.json",
    "artifact.image",
    "artifact.audio",
    "artifact.video",
    "artifact.file",
    "artifact.vector",
    "artifact.tensor",
    "artifact.archive",
    "artifact.provider_resource",
    "artifact.unknown",
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for custom kind defaults."""
    # Each test implementation receives its own mapping so structural protocol
    # checks never depend on mutable default data shared between instances.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Immutable custom kind proving inheritance-free implementation."""

    id: OpenIdentifier
    """Standard or provider-defined artifact classification identifier."""

    semantic: str | None = None
    """Optional producer guidance for an unfamiliar classification."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Provider JSON retained without interpretation or execution."""


def _serialize_kind(kind: ArtifactKind) -> dict[str, JsonValue]:
    """Serialize one artifact kind into its language-neutral public shape."""
    document: dict[str, JsonValue] = {"id": kind.id.value}

    # Optional semantics and provider extensions remain independent fields. The
    # serializer does not infer either value from a standard or unknown ID.
    if kind.semantic is not None:
        document["semantic"] = kind.semantic
    if kind.extensions:
        document["extensions"] = dict(kind.extensions)
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded kind field."""
    # Reject scalars and arrays before reconstruction so host languages cannot
    # introduce incompatible coercion rules for named public kind fields.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded kind field."""
    # Exact string membership preserves identifier and semantic code points;
    # numbers, booleans, null, and containers are never converted to text.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_kind(document: dict[str, JsonValue]) -> _Kind:
    """Reconstruct one custom kind from its language-neutral public shape."""
    semantic_value = document.get("semantic")

    # Reconstruction deliberately avoids a known-kind lookup. Unknown identity,
    # optional semantics, and provider data therefore survive as supplied.
    return _Kind(
        id=OpenIdentifier(_require_string(document.get("id"), "id")),
        semantic=(
            _require_string(semantic_value, "semantic")
            if semantic_value is not None
            else None
        ),
        extensions=(
            _require_object(document.get("extensions"), "extensions")
            if "extensions" in document
            else {}
        ),
    )


def test_artifact_kind_accepts_every_standard_identifier() -> None:
    """Verify all declared standard classifications share one open contract."""
    kinds = tuple(_Kind(OpenIdentifier(value)) for value in _STANDARD_KINDS)

    # Structural recognition requires neither SDK inheritance nor registration;
    # every standard identity remains exact and independently distinguishable.
    assert all(isinstance(kind, ArtifactKind) for kind in kinds)
    assert tuple(kind.id.value for kind in kinds) == _STANDARD_KINDS
    assert len({kind.id for kind in kinds}) == len(_STANDARD_KINDS)


def test_artifact_kind_preserves_unknown_kind_fields() -> None:
    """Verify unknown identity, semantics, and extensions remain observable."""
    identifier = OpenIdentifier("vendor.depth_map")
    extensions: Extensions = {
        "vendor.dimensions": 3,
        "vendor.coordinateSystem": "right-handed",
    }
    kind = _Kind(
        id=identifier,
        semantic="A provider depth map artifact.",
        extensions=extensions,
    )

    # An unknown kind is not collapsed to artifact.unknown or treated as a
    # processing capability; all producer-supplied classification data remains.
    assert isinstance(kind, ArtifactKind)
    assert kind.id is identifier
    assert kind.id.value == "vendor.depth_map"
    assert kind.semantic == "A provider depth map artifact."
    assert kind.extensions is extensions


def test_artifact_kind_round_trips_unknown_kind_through_json() -> None:
    """Verify provider kind data survives ordinary portable JSON encoding."""
    kind = _Kind(
        id=OpenIdentifier("vendor.depth_map"),
        semantic="A provider depth map artifact.",
        extensions={
            "vendor.dimensions": 3,
            "vendor.axes": ["x", "y", "depth"],
        },
    )

    # Encoding and decoding real JSON proves fidelity does not depend on the
    # original Python object or shared mapping references.
    encoded = json.dumps(_serialize_kind(kind), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_kind(_require_object(decoded, "kind"))

    assert restored == kind
    assert restored.id is not kind.id
    assert restored.extensions is not kind.extensions
    assert _serialize_kind(restored) == _serialize_kind(kind)


def test_artifact_kind_requires_the_complete_structural_surface() -> None:
    """Verify identity alone cannot satisfy lossless unknown-kind semantics."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteKind:
        """Intentionally omit semantic and extension properties."""

        id: OpenIdentifier
        """Classification identity without forward-compatible fields."""

    incomplete = _IncompleteKind(OpenIdentifier("artifact.text"))

    # Optional semantic content may be None and extensions may be empty, but the
    # properties must exist so consumers can use one stable read-only surface.
    assert not isinstance(incomplete, ArtifactKind)
    assert not isinstance(cast(object, OpenIdentifier("artifact.text")), ArtifactKind)
