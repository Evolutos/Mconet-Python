"""Aggregate and invariant tests for immutable capability resolution results."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field, fields
from typing import cast

from mconet.core.domain import (
    Diagnostic,
    Extensions,
    InteractionPhase,
    OpenIdentifier,
)
from mconet.core.spi import (
    CapabilityRequirement,
    CapabilityResolution,
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
        # Match aggregate-owned wording so nested fixture failures cannot make a
        # malformed collection test pass for an unrelated reason.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for protocol fixtures."""
    # Fresh mappings prevent otherwise separate requirements and capabilities
    # from sharing mutable test setup state through default values.
    return {}


@dataclass(frozen=True, slots=True)
class _Requirement:
    """Complete capability requirement used by aggregate result tests."""

    capability_id: OpenIdentifier
    """Open identity requested by one interaction input."""

    required: bool
    """Whether unsupported resolution must fail the interaction."""

    constraints: Extensions = field(default_factory=_empty_extensions)
    """Portable matching facts retained in the aggregate."""

    source_path: str | None = None
    """Optional diagnostic origin retained in the aggregate."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown requirement data retained in the aggregate."""


@dataclass(frozen=True, slots=True)
class _Capability:
    """Complete capability declaration used by satisfaction fixtures."""

    id: OpenIdentifier
    """Open identity offered by one selected provider."""

    version: str | None = None
    """Optional producer version retained in the nested result."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Portable provider facts retained in the nested result."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown declaration data retained in the nested result."""


@dataclass(frozen=True, slots=True)
class _IncompleteRequirement:
    """Requirement-like object lacking the complete structural surface."""

    capability_id: OpenIdentifier
    """Identity alone cannot represent an unsupported requirement."""


@dataclass(frozen=True, slots=True)
class _MalformedRequiredness:
    """Complete structural requirement returning non-boolean requiredness."""

    capability_id: OpenIdentifier
    """Valid open identity retained to isolate requiredness validation."""

    required: object
    """Invalid dynamic value used to exercise exact bool validation."""

    constraints: Extensions
    """Valid constraints retained to isolate requiredness validation."""

    source_path: str | None
    """Valid path retained to isolate requiredness validation."""

    extensions: Extensions
    """Valid extensions retained to isolate requiredness validation."""


def _requirement(identifier: str, *, required: bool) -> _Requirement:
    """Build one complete distinguishable capability requirement."""
    # Source path and constraint facts make identity preservation observable
    # without adding a separate fake collector or resolver to this value test.
    return _Requirement(
        capability_id=OpenIdentifier(identifier),
        required=required,
        constraints={"variant": "fixture"},
        source_path=f"task.requirements.{identifier}",
        extensions={"origin": "test"},
    )


def _satisfied(identifier: str, provider_id: str) -> SatisfiedCapability:
    """Build one complete satisfaction for an ordered aggregate fixture."""
    requirement = _requirement(identifier, required=True)
    capability = _Capability(
        OpenIdentifier(identifier),
        version="2026-10",
        attributes={"supported": True},
    )

    # Construct through the public nested value so its protocol and matching-ID
    # invariants are proven before aggregate validation observes it.
    return SatisfiedCapability(requirement, capability, provider_id)


def _diagnostic(code: str) -> Diagnostic:
    """Build one non-secret capability-resolution diagnostic."""
    # Distinct codes make deterministic diagnostic order directly observable.
    return Diagnostic(
        code=code,
        severity="warning",
        phase=InteractionPhase(OpenIdentifier("capability_resolution")),
        message="Optional capability is unavailable.",
    )


def test_capability_resolution_defaults_to_complete_empty_result() -> None:
    """Verify absence of requirements produces explicit immutable collections."""
    resolution = CapabilityResolution()

    # Empty tuples represent successful resolution with no capability facts;
    # None would force every consumer to invent missing-result semantics.
    assert resolution.satisfied == ()
    assert resolution.optional_unsupported == ()
    assert resolution.diagnostics == ()


def test_capability_resolution_preserves_membership_identity_and_order() -> None:
    """Verify all three resolver outputs remain exact and independently ordered."""
    first_satisfied = _satisfied("model.text.output", "builtin.text")
    second_satisfied = _satisfied("model.tool.calling", "plugin.tools")
    first_optional = _requirement("transport.sse", required=False)
    second_optional = _requirement("vendor.response.citations", required=False)
    first_diagnostic = _diagnostic("optional_sse_unsupported")
    second_diagnostic = _diagnostic("optional_citations_unsupported")

    resolution = CapabilityResolution(
        satisfied=(first_satisfied, second_satisfied),
        optional_unsupported=(first_optional, second_optional),
        diagnostics=(first_diagnostic, second_diagnostic),
    )

    # Aggregate construction neither sorts, copies members, merges diagnostics,
    # nor flattens nested requirement/capability facts.
    assert resolution.satisfied[0] is first_satisfied
    assert resolution.satisfied[1] is second_satisfied
    assert resolution.optional_unsupported[0] is first_optional
    assert resolution.optional_unsupported[1] is second_optional
    assert resolution.diagnostics[0] is first_diagnostic
    assert resolution.diagnostics[1] is second_diagnostic


def test_capability_resolution_requires_tuple_collections() -> None:
    """Verify caller-owned mutable lists cannot become result membership."""
    satisfied = _satisfied("model.text.output", "provider")
    optional = _requirement("transport.sse", required=False)
    diagnostic = _diagnostic("optional_sse_unsupported")

    # Each field reports its own boundary failure before member validation so a
    # list cannot be mutated after the execution snapshot retains this result.
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(
            satisfied=cast(tuple[SatisfiedCapability, ...], [satisfied])
        ),
        "satisfied must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(
            optional_unsupported=cast(
                tuple[CapabilityRequirement, ...],
                [optional],
            )
        ),
        "optional_unsupported must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(
            diagnostics=cast(tuple[Diagnostic, ...], [diagnostic])
        ),
        "diagnostics must be a tuple",
    )


def test_capability_resolution_requires_typed_members() -> None:
    """Verify each collection accepts only its dedicated completed values."""
    optional = _requirement("transport.sse", required=False)

    # Similar or arbitrary objects cannot cross nominal result and diagnostic
    # boundaries, while optional requirements retain their structural protocol.
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(satisfied=(cast(SatisfiedCapability, optional),)),
        "satisfied must contain SatisfiedCapability values",
    )
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(
            optional_unsupported=(
                cast(
                    CapabilityRequirement,
                    _IncompleteRequirement(optional.capability_id),
                ),
            )
        ),
        "optional_unsupported must contain CapabilityRequirement values",
    )
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(diagnostics=(cast(Diagnostic, object()),)),
        "diagnostics must contain Diagnostic values",
    )


def test_capability_resolution_optional_unsupported_requires_optional_flag() -> None:
    """Verify required and malformed requirements cannot enter optional output."""
    required = _requirement("transport.sse", required=True)
    malformed = _MalformedRequiredness(
        OpenIdentifier("transport.sse"),
        0,
        {},
        None,
        {},
    )

    # A missing required capability is a resolver error, not a successful result
    # member. Numeric false is rejected even though Python considers it falsy.
    _assert_raises(
        ValueError,
        lambda: CapabilityResolution(optional_unsupported=(required,)),
        "must contain only optional requirements",
    )
    _assert_raises(
        TypeError,
        lambda: CapabilityResolution(
            optional_unsupported=(cast(CapabilityRequirement, malformed),)
        ),
        "required must be a boolean",
    )


def test_capability_resolution_rejects_conflicting_terminal_outcomes() -> None:
    """Verify one exact requirement cannot be both satisfied and unsupported."""
    requirement = _requirement("vendor.response.citations", required=False)
    capability = _Capability(OpenIdentifier("vendor.response.citations"))
    satisfied = SatisfiedCapability(requirement, capability, "provider")

    # Identity comparison protects one collected fact without imposing equality,
    # deduplication, or source-path policy on distinct protocol implementations.
    _assert_raises(
        ValueError,
        lambda: CapabilityResolution(
            satisfied=(satisfied,),
            optional_unsupported=(requirement,),
        ),
        "cannot be both satisfied and optional unsupported",
    )


def test_capability_resolution_has_frozen_exact_field_surface() -> None:
    """Verify only completed aggregate outputs form the public value."""
    resolution = CapabilityResolution()

    # Resolver inputs, providers, policy, errors, and extension mechanisms remain
    # outside this result rather than becoming hidden mutable execution state.
    assert tuple(field.name for field in fields(CapabilityResolution)) == (
        "satisfied",
        "optional_unsupported",
        "diagnostics",
    )
    assert not hasattr(resolution, "requirements")
    assert not hasattr(resolution, "providers")
    assert not hasattr(resolution, "policy")
    assert not hasattr(resolution, "error")
    assert not hasattr(resolution, "extensions")
    _assert_raises(
        FrozenInstanceError,
        lambda: resolution.__setattr__("diagnostics", (_diagnostic("changed"),)),
        "cannot assign to field",
    )


def test_capability_resolution_has_value_equality() -> None:
    """Verify equality includes all aggregate outputs and no hidden resolver state."""
    satisfied = (_satisfied("model.text.output", "provider"),)
    optional = (_requirement("transport.sse", required=False),)
    diagnostics = (_diagnostic("optional_sse_unsupported"),)
    first = CapabilityResolution(satisfied, optional, diagnostics)
    same = CapabilityResolution(satisfied, optional, diagnostics)
    without_diagnostics = CapabilityResolution(satisfied, optional)

    # Dataclass equality composes three immutable collections and cannot observe
    # which resolver instance produced otherwise identical facts.
    assert first == same
    assert first != without_diagnostics
