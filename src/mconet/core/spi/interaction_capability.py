"""Open semantic contract for capabilities available to an interaction."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import Extensions, OpenIdentifier


@runtime_checkable
class InteractionCapability(Protocol):
    """Describe one standard or provider-defined interaction capability.

    Capability identity remains open so SDK components and integrations can
    declare new behavior without changing a Core enumeration or registration
    table. Version, attributes, and extensions describe provider facts only;
    requirements, matching constraints, provider precedence, and resolution
    results belong to their dedicated contracts and deterministic Core logic.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this capability."""
        # A nominal open identifier preserves unknown capability names exactly;
        # this protocol neither validates a known set nor infers support.
        ...

    @property
    def version(self) -> str | None:
        """Return the optional producer-defined capability version."""
        # Version is descriptive compatibility data. Consumers must not derive
        # provider priority or silently reinterpret an absent version here.
        ...

    @property
    def attributes(self) -> Extensions:
        """Return portable facts describing the offered capability."""
        # Attributes report provider facts such as limits or supported variants;
        # matching them against requirement constraints is a separate operation.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned fields preserved for forward compatibility."""
        # Extension data stays observable without expanding this stable protocol
        # for every provider-specific descriptive field.
        ...
