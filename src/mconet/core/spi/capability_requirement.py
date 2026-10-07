"""Open semantic contract for one interaction capability requirement."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import Extensions, OpenIdentifier


@runtime_checkable
class CapabilityRequirement(Protocol):
    """Describe one required or optional capability requested by an interaction.

    Requirements may be produced from a request, task, message, artifact, mode,
    protocol plan, or selected component. This protocol preserves the requested
    open capability identity, portable matching inputs, and diagnostic source;
    it does not evaluate constraints, choose providers, modify the request, or
    record resolution results.
    """

    @property
    def capability_id(self) -> OpenIdentifier:
        """Return the open identifier of the requested capability."""
        # Unknown capability identities remain exact matching inputs rather than
        # being rejected by a closed Core enumeration or normalized to a fallback.
        ...

    @property
    def required(self) -> bool:
        """Return whether absence of a matching provider must fail resolution."""
        # This flag records requirement strength only; compatibility policy owns
        # diagnostics for unsupported optional requirements at resolution time.
        ...

    @property
    def constraints(self) -> Extensions:
        """Return portable constraint facts supplied to capability matching."""
        # Constraints remain declarative JSON data. This boundary defines no
        # expression language, comparison operators, or provider-specific rules.
        ...

    @property
    def source_path(self) -> str | None:
        """Return an optional diagnostic path to the requirement source."""
        # The path explains where collection observed the need; it is not an
        # object reference, mutation address, selection key, or execution command.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned requirement fields for forward compatibility."""
        # Extensions stay visible to newer collectors and resolvers without
        # changing the meaning of capability identity or requiredness.
        ...
