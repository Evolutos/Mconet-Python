"""Immutable results of resolving uniquely selected runtime components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi.component_role import ComponentRole
from mconet.core.spi.selected_component import SelectedComponent


@dataclass(frozen=True, slots=True)
class ComponentSelectionResolution:
    """Store the ordered, role-unique components selected for one interaction.

    ``components`` contains only roles that resolution has reduced to one
    component. Input-dispatched authorization, artifact, collector, and provider
    candidates remain in their dedicated execution-snapshot collections because
    they are not uniquely selected ``ComponentRole`` values at this stage.
    """

    components: tuple[SelectedComponent, ...] = ()
    """Ordered immutable snapshots of components selected for unique roles."""

    def __post_init__(self) -> None:
        """Require immutable membership and at most one component per role."""
        components = cast(object, self.components)

        # Tuple storage fixes both membership and deterministic resolver order;
        # accepting a list would let callers mutate the interaction snapshot.
        if not isinstance(components, tuple):
            raise TypeError("ComponentSelectionResolution components must be a tuple.")

        # Validate members before inspecting their roles so malformed dynamic
        # input receives an error owned by the collection boundary.
        selected_components = cast(tuple[object, ...], components)
        for component in selected_components:
            if not isinstance(component, SelectedComponent):
                raise TypeError(
                    "ComponentSelectionResolution components must contain "
                    "SelectedComponent values."
                )

        # Every ComponentRole represents a single execution-chain position. A
        # second equal role would reintroduce an unresolved ambiguity, while one
        # component instance may still legitimately fulfill two different roles.
        seen_roles: set[ComponentRole] = set()
        for component in cast(tuple[SelectedComponent, ...], components):
            if component.role in seen_roles:
                raise ValueError(
                    "ComponentSelectionResolution components must use unique roles."
                )
            seen_roles.add(component.role)
