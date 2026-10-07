"""Open structural contract tests for capability requirements."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import cast

from mconet.core.domain import Extensions, JsonValue, OpenIdentifier
from mconet.core.spi import CapabilityRequirement


def _empty_extensions() -> Extensions:
    """Create independent empty JSON mappings for requirement fixtures."""
    # A fresh mapping prevents separate custom requirements from sharing mutable
    # fixture state even though consumers use the read-only Extensions surface.
    return {}


@dataclass(frozen=True, slots=True)
class _Requirement:
    """Immutable custom requirement proving inheritance-free implementation."""

    capability_id: OpenIdentifier
    """Open identity of the capability that must be matched."""

    required: bool
    """Whether unsupported resolution must fail the interaction."""

    constraints: Extensions = field(default_factory=_empty_extensions)
    """Portable facts used as deterministic matching inputs."""

    source_path: str | None = None
    """Optional diagnostic location from which collection derived the need."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown requirement fields retained for forward compatibility."""


class _PropertyRequirement:
    """Custom implementation exposing all requirement facts through properties."""

    def __init__(
        self,
        capability_id: OpenIdentifier,
        required: bool,
        constraints: Extensions,
        source_path: str | None,
        extensions: Extensions,
    ) -> None:
        """Store exact requirement inputs behind private implementation state."""
        # Private storage proves the contract depends on properties and types,
        # not dataclass fields, SDK inheritance, or collector-owned base classes.
        self._capability_id = capability_id
        self._required = required
        self._constraints = constraints
        self._source_path = source_path
        self._extensions = extensions

    @property
    def capability_id(self) -> OpenIdentifier:
        """Return the exact requested open capability identity."""
        # No known-identifier lookup or normalization occurs at this boundary.
        return self._capability_id

    @property
    def required(self) -> bool:
        """Return the exact requiredness decision made by the collector."""
        # Provider availability and compatibility policy cannot rewrite this fact.
        return self._required

    @property
    def constraints(self) -> Extensions:
        """Return the exact read-only matching constraint mapping."""
        # Interpretation remains owned by deterministic capability resolution.
        return self._constraints

    @property
    def source_path(self) -> str | None:
        """Return the exact optional diagnostic source path."""
        # The path is descriptive text and never dereferenced or executed here.
        return self._source_path

    @property
    def extensions(self) -> Extensions:
        """Return the exact read-only forward-compatible extension mapping."""
        # Unknown values remain separate from stable matching inputs.
        return self._extensions


def _accept_requirement(
    requirement: CapabilityRequirement,
) -> CapabilityRequirement:
    """Return one value after crossing the statically typed protocol boundary."""
    # Pyright checks exact property types while runtime structural recognition
    # independently proves that custom implementations need no SDK superclass.
    return requirement


def _serialize_requirement(
    requirement: CapabilityRequirement,
) -> dict[str, JsonValue]:
    """Serialize one requirement into its language-neutral public field shape."""
    document: dict[str, JsonValue] = {
        "capabilityId": requirement.capability_id.value,
        "required": requirement.required,
        "constraints": dict(requirement.constraints),
        "extensions": dict(requirement.extensions),
    }

    # Preserve None as field absence rather than inventing an empty path that
    # could be mistaken for an actual root source location by diagnostics.
    if requirement.source_path is not None:
        document["sourcePath"] = requirement.source_path
    return document


def _require_bool(value: JsonValue | None, field_name: str) -> bool:
    """Return one required JSON boolean without numeric coercion."""
    # Exact type avoids treating 0 or 1 as booleans on Python while other target
    # languages keep JSON numbers and booleans as distinct primitive kinds.
    if type(value) is not bool:
        raise AssertionError(f"{field_name} must be a JSON boolean.")
    return value


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued decoded requirement field."""
    # Scalars, arrays, and null cannot become named constraint or extension maps
    # through platform-specific coercion.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required JSON string without implicit conversion."""
    # Reject every non-string JSON form so identity and source paths remain
    # byte-for-byte portable across SDK implementations.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _deserialize_requirement(document: dict[str, JsonValue]) -> _Requirement:
    """Reconstruct a custom requirement without interpreting its constraints."""
    source_path_value = document.get("sourcePath")

    # Rebuild the open identity and each fact independently. The test boundary
    # never selects providers, evaluates expressions, or changes requiredness.
    return _Requirement(
        capability_id=OpenIdentifier(
            _require_string(document.get("capabilityId"), "capabilityId")
        ),
        required=_require_bool(document.get("required"), "required"),
        constraints=_require_object(document.get("constraints"), "constraints"),
        source_path=(
            _require_string(source_path_value, "sourcePath")
            if source_path_value is not None
            else None
        ),
        extensions=_require_object(document.get("extensions"), "extensions"),
    )


def test_capability_requirement_preserves_required_and_optional_decisions() -> None:
    """Verify both requirement strengths use one open structural contract."""
    required = _Requirement(
        OpenIdentifier("model.text.output"),
        True,
        source_path="task.output",
    )
    optional = _Requirement(
        OpenIdentifier("vendor.response.citations"),
        False,
        source_path="task.extensions.citations",
    )

    # Requiredness remains a collector-owned fact. Structural conformance does
    # not infer support, reject an unknown ID, or apply compatibility policy.
    assert isinstance(required, CapabilityRequirement)
    assert isinstance(optional, CapabilityRequirement)
    assert _accept_requirement(required) is required
    assert _accept_requirement(optional) is optional
    assert required.required is True
    assert optional.required is False
    assert optional.capability_id == OpenIdentifier("vendor.response.citations")


def test_capability_requirement_preserves_constraints_and_extensions() -> None:
    """Verify portable matching facts remain separate from unknown fields."""
    constraints: Extensions = MappingProxyType(
        {
            "minimumContextWindow": 128_000,
            "acceptedVariants": ["dense", "hybrid"],
        }
    )
    extensions: Extensions = MappingProxyType(
        {"vendor.regionAffinity": ["ap-east", "eu-central"]}
    )
    requirement = _PropertyRequirement(
        OpenIdentifier("vendor.vector.batch"),
        True,
        constraints,
        "task.nodes.embedding",
        extensions,
    )

    # The protocol exposes exact mappings but does not merge extension data into
    # constraints or evaluate either mapping during structural recognition.
    assert isinstance(requirement, CapabilityRequirement)
    assert _accept_requirement(requirement) is requirement
    assert requirement.constraints is constraints
    assert requirement.extensions is extensions
    assert requirement.source_path == "task.nodes.embedding"


def test_capability_requirement_round_trips_unknown_json_fields() -> None:
    """Verify an unknown constrained requirement survives portable JSON encoding."""
    requirement = _Requirement(
        capability_id=OpenIdentifier("vendor.vector.batch"),
        required=False,
        constraints={"maximumBatchSize": 64, "variant": "hybrid"},
        source_path="task.nodes[0].extensions.batch",
        extensions={"vendor.reason": "throughput"},
    )

    # Real encoding and decoding proves fidelity does not depend on Python object
    # identity, a capability registry, or reuse of the original mapping objects.
    encoded = json.dumps(_serialize_requirement(requirement), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)
    restored = _deserialize_requirement(_require_object(decoded, "requirement"))

    assert isinstance(restored, CapabilityRequirement)
    assert restored == requirement
    assert restored.capability_id is not requirement.capability_id
    assert restored.constraints is not requirement.constraints
    assert restored.extensions is not requirement.extensions
    assert _serialize_requirement(restored) == _serialize_requirement(requirement)


def test_capability_requirement_preserves_absent_source_path() -> None:
    """Verify requirements collected without a path retain explicit absence."""
    requirement = _Requirement(
        OpenIdentifier("interaction.cancellation"),
        True,
    )

    # None means the collector has no portable location to report. Serialization
    # omits the field and reconstruction does not invent an empty or root path.
    document = _serialize_requirement(requirement)
    assert requirement.source_path is None
    assert "sourcePath" not in document
    assert _deserialize_requirement(document).source_path is None


def test_capability_requirement_has_only_collection_facts() -> None:
    """Verify provider declarations and resolution state remain separate."""
    requirement = _Requirement(OpenIdentifier("transport.sse"), True)

    # Attributes/version describe an offered capability; providers, matches, and
    # diagnostics are created only by later declaration and resolution contracts.
    assert tuple(field.name for field in fields(_Requirement)) == (
        "capability_id",
        "required",
        "constraints",
        "source_path",
        "extensions",
    )
    assert not hasattr(requirement, "id")
    assert not hasattr(requirement, "version")
    assert not hasattr(requirement, "attributes")
    assert not hasattr(requirement, "provider_id")
    assert not hasattr(requirement, "matched")
    assert not hasattr(requirement, "diagnostics")


def test_capability_requirement_requires_complete_structural_surface() -> None:
    """Verify partial requirement-like values do not satisfy the protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingSourcePath:
        """Intentionally omit the optional-valued but required property."""

        capability_id: OpenIdentifier
        """Open identity without a complete requirement surface."""

        required: bool
        """Requiredness retained only to isolate the missing property."""

        constraints: Extensions
        """Constraint facts retained only to isolate the missing property."""

        extensions: Extensions
        """Extension facts retained only to isolate the missing property."""

    incomplete = _MissingSourcePath(
        OpenIdentifier("transport.sse"),
        True,
        {},
        {},
    )

    # Optional source content may be None, but the property itself must exist so
    # every collector and resolver observes one stable complete protocol surface.
    assert not isinstance(incomplete, CapabilityRequirement)
    assert not isinstance(
        cast(object, OpenIdentifier("transport.sse")),
        CapabilityRequirement,
    )
