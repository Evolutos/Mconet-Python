"""Immutable facts recording one satisfied interaction capability requirement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi.capability_requirement import CapabilityRequirement
from mconet.core.spi.interaction_capability import InteractionCapability


@dataclass(frozen=True, slots=True)
class SatisfiedCapability:
    """Bind one requirement to the matching capability and provider provenance.

    This value is produced only after deterministic capability resolution has
    accepted the provider declaration for the requirement. It preserves the
    exact input objects and provider label without re-evaluating constraints,
    retaining a provider component, or introducing mutable resolution state.
    """

    requirement: CapabilityRequirement
    """Exact required or optional capability request that was satisfied."""

    capability: InteractionCapability
    """Exact provider declaration accepted for the requirement."""

    provider_id: str
    """Provider provenance label recorded by capability resolution."""

    def __post_init__(self) -> None:
        """Require complete protocols, matching open IDs, and string provenance."""
        requirement = cast(object, self.requirement)
        capability = cast(object, self.capability)
        provider_id = cast(object, self.provider_id)

        # Structural recognition permits collector-owned requirement classes
        # without SDK inheritance while rejecting unrelated partial objects.
        if not isinstance(requirement, CapabilityRequirement):
            raise TypeError(
                "SatisfiedCapability requirement must implement CapabilityRequirement."
            )

        # Capability declarations are equally open structural values; storing
        # the exact implementation preserves all provider attributes/extensions.
        if not isinstance(capability, InteractionCapability):
            raise TypeError(
                "SatisfiedCapability capability must implement InteractionCapability."
            )

        requirement_id = cast(object, requirement.capability_id)
        capability_id = cast(object, capability.id)

        # Runtime-checkable protocols verify property presence but not returned
        # value types. Require nominal identifiers before comparing resolution facts.
        if not isinstance(requirement_id, OpenIdentifier):
            raise TypeError(
                "SatisfiedCapability requirement capability_id must be an "
                "OpenIdentifier."
            )
        if not isinstance(capability_id, OpenIdentifier):
            raise TypeError(
                "SatisfiedCapability capability id must be an OpenIdentifier."
            )

        # A satisfied result cannot pair declarations for different identities;
        # constraint evaluation remains the resolver's already-completed concern.
        if requirement_id != capability_id:
            raise ValueError(
                "SatisfiedCapability requirement and capability IDs must match."
            )

        # Provider ID is resolution provenance, not a registry lookup key or a
        # retained provider instance. Preserve exact text without normalization.
        if not isinstance(provider_id, str):
            raise TypeError("SatisfiedCapability provider_id must be a string.")
