"""Immutable aggregate results produced by capability resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Diagnostic
from mconet.core.spi.capability_requirement import CapabilityRequirement
from mconet.core.spi.satisfied_capability import SatisfiedCapability


@dataclass(frozen=True, slots=True)
class CapabilityResolution:
    """Store all successful and optional-unsupported capability facts.

    Successful entries retain their requirement, accepted declaration, and
    provider provenance. Optional unsupported entries retain exact requirements
    for policy diagnostics. The aggregate records already-completed resolver
    output; it does not select providers, evaluate constraints, retry matching,
    modify requests, or infer additional diagnostics.
    """

    satisfied: tuple[SatisfiedCapability, ...] = ()
    """Ordered immutable capability satisfactions produced by the resolver."""

    optional_unsupported: tuple[CapabilityRequirement, ...] = ()
    """Ordered immutable optional requirements with no matching provider."""

    diagnostics: tuple[Diagnostic, ...] = ()
    """Ordered immutable non-secret observations from capability resolution."""

    def __post_init__(self) -> None:
        """Require immutable typed collections and coherent requirement outcomes."""
        satisfied = cast(object, self.satisfied)
        optional_unsupported = cast(object, self.optional_unsupported)
        diagnostics = cast(object, self.diagnostics)

        # Tuples fix resolver output membership and order before the execution
        # component snapshot can retain this resolution across later stages.
        if not isinstance(satisfied, tuple):
            raise TypeError("CapabilityResolution satisfied must be a tuple.")
        if not isinstance(optional_unsupported, tuple):
            raise TypeError(
                "CapabilityResolution optional_unsupported must be a tuple."
            )
        if not isinstance(diagnostics, tuple):
            raise TypeError("CapabilityResolution diagnostics must be a tuple.")

        satisfied_values = cast(tuple[object, ...], satisfied)
        optional_values = cast(tuple[object, ...], optional_unsupported)
        diagnostic_values = cast(tuple[object, ...], diagnostics)

        # SatisfiedCapability already guarantees complete open protocols, equal
        # capability IDs, and string provider provenance for every success.
        for item in satisfied_values:
            if not isinstance(item, SatisfiedCapability):
                raise TypeError(
                    "CapabilityResolution satisfied must contain "
                    "SatisfiedCapability values."
                )

        # Optional unsupported entries remain open protocol objects. Validate the
        # complete surface before observing requiredness for result semantics.
        for item in optional_values:
            if not isinstance(item, CapabilityRequirement):
                raise TypeError(
                    "CapabilityResolution optional_unsupported must contain "
                    "CapabilityRequirement values."
                )

            required = cast(object, item.required)
            # Protocol runtime checks only property presence. Exact bool rejects
            # numeric and arbitrary dynamic substitutes before branching.
            if type(required) is not bool:
                raise TypeError(
                    "CapabilityResolution optional_unsupported requirement "
                    "required must be a boolean."
                )
            if required:
                raise ValueError(
                    "CapabilityResolution optional_unsupported must contain only "
                    "optional requirements."
                )

        # Diagnostics are completed nominal values whose constructors already
        # enforce non-secret portable field and structured-detail constraints.
        for item in diagnostic_values:
            if not isinstance(item, Diagnostic):
                raise TypeError(
                    "CapabilityResolution diagnostics must contain Diagnostic values."
                )

        # One exact collected requirement cannot have two terminal outcomes in
        # the same resolution. Identity avoids inventing semantic deduplication
        # rules for distinct collector-produced protocol objects.
        satisfied_requirement_ids = {
            id(item.requirement)
            for item in cast(tuple[SatisfiedCapability, ...], satisfied)
        }
        if any(id(item) in satisfied_requirement_ids for item in optional_values):
            raise ValueError(
                "CapabilityResolution requirement cannot be both satisfied and "
                "optional unsupported."
            )
