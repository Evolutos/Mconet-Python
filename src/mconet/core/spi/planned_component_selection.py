"""Immutable role requirements for one planned runtime component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi.component_role import ComponentRole


@dataclass(frozen=True, slots=True)
class PlannedComponentSelection:
    """Describe one role's presence and capability requirements.

    ``required`` controls whether resolution may omit the role. Capability
    membership constrains any selected component independently of that presence
    policy. This value does not carry a component instance or resolver result.
    """

    role: ComponentRole
    """Execution-chain position for which a component may be selected."""

    required: bool
    """Whether absence of a compatible component must fail resolution."""

    required_capabilities: frozenset[OpenIdentifier] = frozenset()
    """Immutable capabilities every selected component for the role must declare."""

    def __post_init__(self) -> None:
        """Require a nominal role, exact boolean, and immutable capability set."""
        role = cast(object, self.role)
        required = cast(object, self.required)
        required_capabilities = cast(object, self.required_capabilities)

        # Require the validated open role value so plan entries cannot use a bare
        # identifier or string as a substitute for execution-chain position.
        if not isinstance(role, ComponentRole):
            raise TypeError("PlannedComponentSelection role must be a ComponentRole.")

        # Exact membership excludes integers because Python otherwise treats 0
        # and 1 as bool subclasses, obscuring explicit presence policy.
        if type(required) is not bool:
            raise TypeError("PlannedComponentSelection required must be a boolean.")

        # Frozenset preserves language-neutral Set semantics and prevents the
        # required subset from changing while candidates are being evaluated.
        if not isinstance(required_capabilities, frozenset):
            raise TypeError(
                "PlannedComponentSelection required_capabilities must be a frozenset."
            )
        for capability in cast(frozenset[object], required_capabilities):
            if not isinstance(capability, OpenIdentifier):
                raise TypeError(
                    "PlannedComponentSelection required_capabilities must contain "
                    "OpenIdentifier values."
                )
