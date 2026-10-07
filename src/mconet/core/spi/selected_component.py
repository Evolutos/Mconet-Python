"""Immutable snapshots of runtime components selected for execution roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_role import ComponentRole
from mconet.core.spi.runtime_component import RuntimeComponent


@dataclass(frozen=True, slots=True)
class SelectedComponent:
    """Bind one execution role to a component and its metadata snapshot.

    Python's structural ``RuntimeComponent`` protocol provides the language's
    type-erased component boundary. The explicit descriptor records the exact
    immutable metadata used when the component was selected, without adding a
    registry ID, serialization contract, or component lifecycle operation.
    """

    role: ComponentRole
    """Execution-chain position fulfilled by the selected component."""

    component: RuntimeComponent
    """Type-erased runtime component retained for execution."""

    descriptor: ComponentDescriptor
    """Immutable metadata snapshot associated with the selected component."""

    def __post_init__(self) -> None:
        """Require a valid role, component boundary, and matching descriptor."""
        role = cast(object, self.role)
        component = cast(object, self.component)
        descriptor = cast(object, self.descriptor)

        # Keep role identity in the validated value type so the snapshot cannot
        # confuse a role with a bare identifier, component name, or registry key.
        if not isinstance(role, ComponentRole):
            raise TypeError("SelectedComponent role must be a ComponentRole.")

        # RuntimeComponent is runtime-checkable and structural: application and
        # plugin objects need only expose descriptor metadata, not inherit from
        # an SDK base class or opt into a registration mechanism.
        if not isinstance(component, RuntimeComponent):
            raise TypeError("SelectedComponent component must be a RuntimeComponent.")

        # Validate the supplied snapshot before comparing it with the component
        # so malformed external values receive an error owned by this field.
        if not isinstance(descriptor, ComponentDescriptor):
            raise TypeError(
                "SelectedComponent descriptor must be a ComponentDescriptor."
            )

        # The separate descriptor is a selection-time snapshot, not independent
        # caller metadata. Equality permits a computed equivalent descriptor but
        # rejects stale or unrelated metadata before the execution chain uses it.
        component_descriptor = cast(object, component.descriptor)
        if not isinstance(component_descriptor, ComponentDescriptor):
            raise TypeError(
                "SelectedComponent component descriptor must be a ComponentDescriptor."
            )
        if component_descriptor != descriptor:
            raise ValueError(
                "SelectedComponent descriptor must match the component descriptor."
            )
