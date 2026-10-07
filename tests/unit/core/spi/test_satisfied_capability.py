"""Composition tests for immutable satisfied capability facts."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field, fields
from typing import cast

from mconet.core.domain import Extensions, OpenIdentifier
from mconet.core.spi import (
    CapabilityRequirement,
    InteractionCapability,
    SatisfiedCapability,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match result-owned wording so malformed fixture construction cannot
        # accidentally satisfy a negative composition assertion.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Fresh dictionaries prevent test values from sharing mutable setup state
    # while still satisfying each protocol's read-only Mapping annotation.
    return {}


@dataclass(frozen=True, slots=True)
class _Requirement:
    """Complete collector-owned capability requirement fixture."""

    capability_id: OpenIdentifier
    """Open capability identity requested by the interaction."""

    required: bool
    """Whether missing support must fail later resolution."""

    constraints: Extensions = field(default_factory=_empty_extensions)
    """Portable matching facts retained by the result."""

    source_path: str | None = None
    """Optional diagnostic origin of the requirement."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown requirement data retained through composition."""


@dataclass(frozen=True, slots=True)
class _Capability:
    """Complete provider-owned capability declaration fixture."""

    id: OpenIdentifier
    """Open identity of the offered interaction capability."""

    version: str | None = None
    """Optional producer-defined capability version."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Portable facts describing the provider offer."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown provider declaration data retained through composition."""


@dataclass(frozen=True, slots=True)
class _IncompleteRequirement:
    """Requirement-like fixture missing the complete protocol surface."""

    capability_id: OpenIdentifier
    """Identity alone cannot form a complete capability requirement."""


@dataclass(frozen=True, slots=True)
class _IncompleteCapability:
    """Capability-like fixture missing the complete protocol surface."""

    id: OpenIdentifier
    """Identity alone cannot form a complete capability declaration."""


@dataclass(frozen=True, slots=True)
class _MalformedRequirement:
    """Structurally complete requirement returning a non-nominal ID."""

    capability_id: object
    """Invalid dynamic identity used to verify result-boundary defense."""

    required: bool
    """Valid requiredness retained to isolate the identity error."""

    constraints: Extensions
    """Valid constraints retained to isolate the identity error."""

    source_path: str | None
    """Valid source path retained to isolate the identity error."""

    extensions: Extensions
    """Valid extensions retained to isolate the identity error."""


@dataclass(frozen=True, slots=True)
class _MalformedCapability:
    """Structurally complete capability returning a non-nominal ID."""

    id: object
    """Invalid dynamic identity used to verify result-boundary defense."""

    version: str | None
    """Valid version retained to isolate the identity error."""

    attributes: Extensions
    """Valid attributes retained to isolate the identity error."""

    extensions: Extensions
    """Valid extensions retained to isolate the identity error."""


def _requirement(identifier: str = "model.text.output") -> _Requirement:
    """Build one distinguishable complete requirement for composition tests."""
    # Non-empty constraints and source facts make it observable that the result
    # retains the exact object rather than reconstructing only its identity.
    return _Requirement(
        capability_id=OpenIdentifier(identifier),
        required=True,
        constraints={"minimumTokens": 1},
        source_path="task.output",
        extensions={"collector": "task"},
    )


def _capability(identifier: str = "model.text.output") -> _Capability:
    """Build one distinguishable complete provider declaration for tests."""
    # Version, attributes, and extensions prove the composition retains all
    # declaration facts without copying them into separate result fields.
    return _Capability(
        id=OpenIdentifier(identifier),
        version="2026-10",
        attributes={"maximumTokens": 4096},
        extensions={"provider": "fixture"},
    )


def test_satisfied_capability_preserves_exact_resolution_inputs() -> None:
    """Verify requirement, capability, and provider provenance remain exact."""
    requirement = _requirement()
    capability = _capability()

    result = SatisfiedCapability(requirement, capability, "builtin.text-provider")

    # Identity retention keeps every open protocol field available without
    # flattening it into the result or reconstructing a provider declaration.
    assert result.requirement is requirement
    assert result.capability is capability
    assert result.provider_id == "builtin.text-provider"
    assert result.requirement.constraints == {"minimumTokens": 1}
    assert result.requirement.source_path == "task.output"
    assert result.capability.version == "2026-10"
    assert result.capability.attributes == {"maximumTokens": 4096}


def test_satisfied_capability_accepts_unknown_matching_identity() -> None:
    """Verify provider-defined capability IDs need no Core registration."""
    requirement = _requirement("vendor.vector.batch")
    capability = _capability("vendor.vector.batch")

    result = SatisfiedCapability(requirement, capability, "plugin.vector-provider")

    # The result compares nominal open identifiers but never checks a closed list
    # of known capabilities or interprets provider-specific attributes.
    assert result.requirement.capability_id == OpenIdentifier("vendor.vector.batch")
    assert result.capability.id == OpenIdentifier("vendor.vector.batch")
    assert result.provider_id == "plugin.vector-provider"


def test_satisfied_capability_rejects_mismatched_identities() -> None:
    """Verify one resolved fact cannot combine different capability names."""
    requirement = _requirement("model.text.output")
    capability = _capability("model.tool.calling")

    # Constraint evaluation is already complete, but capability identity remains
    # an inexpensive local invariant that every valid satisfaction must preserve.
    _assert_raises(
        ValueError,
        lambda: SatisfiedCapability(requirement, capability, "provider"),
        "requirement and capability IDs must match",
    )


def test_satisfied_capability_requires_complete_structural_inputs() -> None:
    """Verify partial requirement and declaration objects are rejected."""
    requirement = _requirement()
    capability = _capability()

    # Structural protocols permit custom classes, but all documented properties
    # are mandatory even when their values are empty or None.
    _assert_raises(
        TypeError,
        lambda: SatisfiedCapability(
            cast(
                CapabilityRequirement, _IncompleteRequirement(requirement.capability_id)
            ),
            capability,
            "provider",
        ),
        "requirement must implement CapabilityRequirement",
    )
    _assert_raises(
        TypeError,
        lambda: SatisfiedCapability(
            requirement,
            cast(InteractionCapability, _IncompleteCapability(capability.id)),
            "provider",
        ),
        "capability must implement InteractionCapability",
    )


def test_satisfied_capability_requires_nominal_open_identifiers() -> None:
    """Verify dynamic structural objects cannot return primitive ID substitutes."""
    requirement = _requirement()
    capability = _capability()
    malformed_requirement = _MalformedRequirement(
        "model.text.output",
        True,
        {},
        None,
        {},
    )
    malformed_capability = _MalformedCapability(
        "model.text.output",
        None,
        {},
        {},
    )

    # Runtime-checkable protocols only verify attribute presence, so the result
    # boundary nominally checks both identifiers before comparing them.
    _assert_raises(
        TypeError,
        lambda: SatisfiedCapability(
            cast(CapabilityRequirement, malformed_requirement),
            capability,
            "provider",
        ),
        "requirement capability_id must be an OpenIdentifier",
    )
    _assert_raises(
        TypeError,
        lambda: SatisfiedCapability(
            requirement,
            cast(InteractionCapability, malformed_capability),
            "provider",
        ),
        "capability id must be an OpenIdentifier",
    )


def test_satisfied_capability_requires_string_provider_provenance() -> None:
    """Verify provider provenance cannot be an instance or numeric lookup key."""
    requirement = _requirement()
    capability = _capability()

    # The result records only diagnostic provenance text. It neither retains a
    # provider component nor introduces an integer or object registry identity.
    _assert_raises(
        TypeError,
        lambda: SatisfiedCapability(requirement, capability, cast(str, 1)),
        "provider_id must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: SatisfiedCapability(
            requirement,
            capability,
            cast(str, object()),
        ),
        "provider_id must be a string",
    )


def test_satisfied_capability_has_frozen_exact_field_surface() -> None:
    """Verify the result stores only the three completed resolution facts."""
    result = SatisfiedCapability(_requirement(), _capability(), "provider")

    # Matching scores, diagnostics, provider instances, and resolver policy stay
    # outside this focused value instead of becoming duplicate state.
    assert tuple(field.name for field in fields(SatisfiedCapability)) == (
        "requirement",
        "capability",
        "provider_id",
    )
    assert not hasattr(result, "provider")
    assert not hasattr(result, "score")
    assert not hasattr(result, "diagnostics")
    assert not hasattr(result, "matched")
    assert not hasattr(result, "extensions")
    _assert_raises(
        FrozenInstanceError,
        lambda: result.__setattr__("provider_id", "changed"),
        "cannot assign to field",
    )


def test_satisfied_capability_has_value_equality() -> None:
    """Verify equality contains all three fields and no hidden resolver state."""
    requirement = _requirement()
    capability = _capability()
    first = SatisfiedCapability(requirement, capability, "provider")
    same = SatisfiedCapability(requirement, capability, "provider")
    other_provider = SatisfiedCapability(requirement, capability, "other")

    # Dataclass equality composes the public facts only; it does not observe the
    # resolver instance, candidate order, policy, or execution context.
    assert first == same
    assert first != other_provider
