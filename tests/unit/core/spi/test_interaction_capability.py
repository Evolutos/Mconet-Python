"""Open structural contract tests for interaction capabilities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import cast

from mconet.core.domain import Extensions, JsonValue, OpenIdentifier
from mconet.core.spi import InteractionCapability

_STANDARD_CAPABILITY_IDS = (
    "model.text.input",
    "model.text.output",
    "model.tool.calling",
    "interaction.streaming",
    "interaction.client-streaming",
    "interaction.cancellation",
    "transport.sse",
    "transport.websocket",
    "transport.duplex",
    "codec.json-schema",
    "artifact.inline",
    "artifact.streaming",
    "artifact.upload",
    "artifact.transform",
    "authorization.body-signing.precomputed",
    "authorization.body-signing.unsigned",
    "authorization.body-signing.buffered",
    "authorization.body-signing.chunked",
)


def _empty_extensions() -> Extensions:
    """Create independent empty JSON mappings for capability fixtures."""
    # Each custom implementation owns its mapping so protocol conformance never
    # depends on shared mutable default state between otherwise separate values.
    return {}


@dataclass(frozen=True, slots=True)
class _Capability:
    """Immutable custom capability proving inheritance-free implementation."""

    id: OpenIdentifier
    """Standard or provider-defined capability identity."""

    version: str | None = None
    """Optional producer version retained without interpretation."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Portable facts describing the offered capability."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown provider fields preserved for forward compatibility."""


class _PropertyCapability:
    """Custom implementation exposing the contract through properties."""

    def __init__(
        self,
        identifier: OpenIdentifier,
        version: str | None,
        attributes: Extensions,
        extensions: Extensions,
    ) -> None:
        """Store exact capability facts behind private implementation state."""
        # Separate fields prove the protocol does not depend on dataclasses,
        # public writable storage, an SDK base class, or a registry-created type.
        self._id = identifier
        self._version = version
        self._attributes = attributes
        self._extensions = extensions

    @property
    def id(self) -> OpenIdentifier:
        """Return the exact open capability identifier."""
        # Identity crosses the protocol boundary without known-value lookup.
        return self._id

    @property
    def version(self) -> str | None:
        """Return the exact optional producer version."""
        # None remains distinct from an empty or inferred version string.
        return self._version

    @property
    def attributes(self) -> Extensions:
        """Return the exact read-only descriptive attribute mapping."""
        # The producer owns mapping construction; the protocol only exposes its
        # read-only interface and does not convert facts into requirements.
        return self._attributes

    @property
    def extensions(self) -> Extensions:
        """Return the exact read-only forward-compatible extension mapping."""
        # Unknown fields stay separate from stable attributes and remain opaque.
        return self._extensions


def _accept_capability(capability: InteractionCapability) -> InteractionCapability:
    """Return one value after crossing the statically typed protocol boundary."""
    # Pyright verifies all property types while runtime-checkable Protocol
    # recognition independently proves that application implementations need no base.
    return capability


def _serialize_capability(
    capability: InteractionCapability,
) -> dict[str, JsonValue]:
    """Serialize one capability into its language-neutral public field shape."""
    document: dict[str, JsonValue] = {
        "id": capability.id.value,
        "attributes": dict(capability.attributes),
        "extensions": dict(capability.extensions),
    }

    # Preserve absence as absence rather than inventing a default version or
    # coupling serialization to a provider-specific version comparison policy.
    if capability.version is not None:
        document["version"] = capability.version
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded capability field."""
    # Exact JSON object shape avoids platform-dependent coercion from arrays,
    # scalars, or null into named attribute and extension mappings.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued decoded capability field."""
    # Do not stringify numbers, booleans, containers, or null because doing so
    # would create cross-language identity and version differences.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_capability(document: dict[str, JsonValue]) -> _Capability:
    """Reconstruct a custom capability without known-identifier lookup."""
    version_value = document.get("version")

    # Rebuild every field independently so attributes never become matching
    # constraints and unknown extensions never become executable instructions.
    return _Capability(
        id=OpenIdentifier(_require_string(document.get("id"), "id")),
        version=(
            _require_string(version_value, "version")
            if version_value is not None
            else None
        ),
        attributes=_require_object(document.get("attributes"), "attributes"),
        extensions=_require_object(document.get("extensions"), "extensions"),
    )


def test_interaction_capability_accepts_all_standard_identifiers() -> None:
    """Verify documented capabilities share one open structural contract."""
    capabilities = tuple(
        _Capability(OpenIdentifier(identifier))
        for identifier in _STANDARD_CAPABILITY_IDS
    )

    # Structural conformance requires no SDK inheritance or registration, and
    # every identity remains exact instead of collapsing into a closed enum.
    assert all(isinstance(item, InteractionCapability) for item in capabilities)
    assert all(_accept_capability(item) is item for item in capabilities)
    assert tuple(item.id.value for item in capabilities) == _STANDARD_CAPABILITY_IDS
    assert len({item.id for item in capabilities}) == len(_STANDARD_CAPABILITY_IDS)


def test_interaction_capability_preserves_unknown_complete_shape() -> None:
    """Verify unknown identity, version, attributes, and extensions remain exact."""
    attributes: Extensions = MappingProxyType(
        {
            "maxBatchSize": 64,
            "variants": ["dense", "sparse"],
        }
    )
    extensions: Extensions = MappingProxyType(
        {"vendor.routing": {"regions": ["ap-east", "eu-central"]}}
    )
    capability = _PropertyCapability(
        OpenIdentifier("vendor.vector.batch"),
        "2026-10",
        attributes,
        extensions,
    )

    # The protocol preserves producer data but does not claim current Runtime
    # support, translate attributes into constraints, or select a provider.
    assert isinstance(capability, InteractionCapability)
    assert _accept_capability(capability) is capability
    assert capability.id == OpenIdentifier("vendor.vector.batch")
    assert capability.version == "2026-10"
    assert capability.attributes is attributes
    assert capability.extensions is extensions


def test_interaction_capability_round_trips_unknown_json_fields() -> None:
    """Verify the complete open capability survives portable JSON encoding."""
    capability = _Capability(
        id=OpenIdentifier("vendor.vector.batch"),
        version="2026-10",
        attributes={"maxBatchSize": 64, "supportsSparse": True},
        extensions={"vendor.mode": "hybrid"},
    )

    # A real encode/decode cycle proves preservation does not depend on the
    # original Python object, mapping identity, or a registry of known IDs.
    encoded = json.dumps(_serialize_capability(capability), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_capability(_require_object(decoded, "capability"))

    assert isinstance(restored, InteractionCapability)
    assert restored == capability
    assert restored.id is not capability.id
    assert restored.attributes is not capability.attributes
    assert restored.extensions is not capability.extensions
    assert _serialize_capability(restored) == _serialize_capability(capability)


def test_interaction_capability_keeps_requirement_and_resolution_state_absent() -> None:
    """Verify a capability declaration contains only provider-owned facts."""
    capability = _Capability(OpenIdentifier("model.text.output"))

    # Constraints and required/source path describe a consumer requirement;
    # provider identity and match results belong to later dedicated contracts.
    assert tuple(field.name for field in fields(_Capability)) == (
        "id",
        "version",
        "attributes",
        "extensions",
    )
    assert not hasattr(capability, "capability_id")
    assert not hasattr(capability, "constraints")
    assert not hasattr(capability, "required")
    assert not hasattr(capability, "source_path")
    assert not hasattr(capability, "provider_id")
    assert not hasattr(capability, "matched")


def test_interaction_capability_requires_complete_structural_surface() -> None:
    """Verify partial capability-like values do not satisfy the protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingExtensions:
        """Intentionally omit the required forward-compatible property."""

        id: OpenIdentifier
        """Open capability identity without a complete public surface."""

        version: str | None
        """Optional version retained only to isolate the missing field."""

        attributes: Extensions
        """Descriptive facts without the required extension boundary."""

    incomplete = _MissingExtensions(
        OpenIdentifier("model.text.output"),
        None,
        {},
    )

    # Optional values may be None and mappings may be empty, but all properties
    # must exist so consumers see one stable, lossless structural contract.
    assert not isinstance(incomplete, InteractionCapability)
    assert not isinstance(
        cast(object, OpenIdentifier("model.text.output")),
        InteractionCapability,
    )
