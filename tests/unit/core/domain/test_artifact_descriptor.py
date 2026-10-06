"""Open descriptive contract tests for ArtifactDescriptor implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import ArtifactDescriptor, JsonValue, OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Immutable descriptor proving structural implementation without inheritance."""

    kind: OpenIdentifier
    """Standard or provider-defined descriptor shape identity."""


@dataclass(frozen=True, slots=True)
class _ProviderSpatialDescriptor:
    """Describe provider spatial facts without validating or transforming data."""

    kind: OpenIdentifier
    """Provider-defined descriptor shape identity."""

    width: int
    """Declared horizontal sample count retained as descriptive data."""

    height: int
    """Declared vertical sample count retained as descriptive data."""

    coordinate_space: str
    """Opaque producer coordinate-space name retained without interpretation."""


def _serialize_descriptor(descriptor: ArtifactDescriptor) -> dict[str, JsonValue]:
    """Serialize the common descriptor contract into its portable shape."""
    # Only descriptor classification belongs to the common protocol. Concrete
    # descriptor codecs own modality-specific dimensions and other facts.
    return {"kind": descriptor.kind.value}


def _require_object(value: JsonValue, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded descriptor document."""
    # Requiring named object fields avoids positional modality representations
    # that different language implementations could interpret inconsistently.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded descriptor field."""
    # Descriptor identity preserves exact text; no scalar or composite JSON value
    # is coerced into a string by the language-neutral reconstruction boundary.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_descriptor(document: dict[str, JsonValue]) -> _Descriptor:
    """Reconstruct descriptor identity from its common portable shape."""
    # Unknown shape IDs remain open instead of passing through a registry or
    # collapsing into a generic descriptor with lost producer identity.
    return _Descriptor(
        kind=OpenIdentifier(_require_string(document.get("kind"), "kind"))
    )


def test_artifact_descriptor_supports_modality_specific_facts() -> None:
    """Verify custom modality fields can accompany the common descriptor kind."""
    minimal = _Descriptor(OpenIdentifier("vendor.feature_vector"))
    spatial = _ProviderSpatialDescriptor(
        kind=OpenIdentifier("vendor.spatial_grid"),
        width=640,
        height=480,
        coordinate_space="camera-local",
    )

    # Structural conformance requires no SDK inheritance. Additional values stay
    # immutable description facts and do not expand the common protocol surface.
    assert isinstance(minimal, ArtifactDescriptor)
    assert isinstance(spatial, ArtifactDescriptor)
    assert minimal.kind.value == "vendor.feature_vector"
    assert spatial.kind.value == "vendor.spatial_grid"
    assert (spatial.width, spatial.height) == (640, 480)
    assert spatial.coordinate_space == "camera-local"


def test_artifact_descriptor_preserves_unknown_kind_through_json() -> None:
    """Verify an unknown descriptor identity survives a portable JSON round trip."""
    descriptor = _Descriptor(OpenIdentifier("vendor.hyperspectral_cube"))

    # Real JSON encoding and reconstruction prove fidelity does not depend on the
    # original Python object or its OpenIdentifier reference.
    encoded = json.dumps(_serialize_descriptor(descriptor), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_descriptor(_require_object(decoded, "descriptor"))

    assert isinstance(restored, ArtifactDescriptor)
    assert restored == descriptor
    assert restored.kind is not descriptor.kind
    assert restored.kind.value == "vendor.hyperspectral_cube"


def test_artifact_descriptor_protocol_declares_only_shape_identity() -> None:
    """Verify the common contract contains neither modality fields nor behavior."""
    declared_properties = {
        name
        for name, value in vars(ArtifactDescriptor).items()
        if isinstance(value, property)
    }
    declared_operations = {
        name
        for name, value in vars(ArtifactDescriptor).items()
        if not name.startswith("_") and callable(value)
    }

    # Exact surface checks keep concrete image, audio, video, vector, validation,
    # and transformation concerns out of the open common descriptor boundary.
    assert declared_properties == {"kind"}
    assert declared_operations == set()


def test_artifact_descriptor_requires_kind_identity() -> None:
    """Verify arbitrary modality facts cannot satisfy the descriptor protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingKind:
        """Intentionally expose dimensions without descriptor classification."""

        dimensions: int
        """A modality fact that cannot substitute for open shape identity."""

    candidate = _MissingKind(1_024)

    # Concrete facts and a bare OpenIdentifier are both incomplete because the
    # descriptor object itself must expose the named kind property.
    assert not isinstance(candidate, ArtifactDescriptor)
    assert not isinstance(
        cast(object, OpenIdentifier("vendor.feature_vector")), ArtifactDescriptor
    )
