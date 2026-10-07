"""Deterministic internal selection for one single-value component role."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.spi import ComponentRole, RuntimeComponent, SelectedComponent


def select_single_component(
    role: ComponentRole,
    layers: ComponentSourceLayers,
    matches: Callable[[RuntimeComponent], bool],
) -> SelectedComponent | None:
    """Select one component only when the highest present layer is unique.

    The four source layers are already ordered as Interaction, Client,
    Integration Plan, and SDK Default. Selection stops at the first non-empty
    layer, applies the Core-owned role condition only within that layer, and
    produces a ``SelectedComponent`` snapshot only for exactly one match. Zero
    or multiple matches produce ``None`` for the following dedicated error
    branches to interpret.

    Type contracts, capabilities, media types, schemas, transport kinds, and
    behavior protocols remain outside the generic algorithm and are expressed
    by its internal pure ``matches`` input. This function does not construct
    stable missing/ambiguity errors, examine lower layers after precedence is
    fixed, invoke component behavior, or consult component names as identifiers.
    """
    role_value = cast(object, role)
    layer_value = cast(object, layers)

    # Keep the nominal role boundary before constructing a SelectedComponent so
    # a bare identifier or string cannot become an execution-chain position.
    if not isinstance(role_value, ComponentRole):
        raise TypeError("role must be a ComponentRole.")
    if not callable(matches):
        raise TypeError("matches must be callable.")

    # Source precedence is encoded by exactly four tuple positions. Rejecting
    # lists, shortened tuples, and expanded tuples prevents caller mutation or a
    # second undocumented priority scheme from entering the fixed resolver.
    if not isinstance(layer_value, tuple):
        raise TypeError("layers must be a tuple.")
    source_values = cast(tuple[object, ...], layer_value)
    if len(source_values) != 4:
        raise ValueError("layers must contain exactly four source layers.")

    validated_layers = source_values
    for layer in validated_layers:
        # Every layer remains an immutable ordered candidate set. Validate the
        # full shape before selection so even a shadowed malformed source cannot
        # survive into later Client validation or execution planning.
        if not isinstance(layer, tuple):
            raise TypeError("each component source layer must be a tuple.")
        for component in cast(tuple[object, ...], layer):
            if not isinstance(component, RuntimeComponent):
                raise TypeError(
                    "component source layers must contain RuntimeComponent values."
                )

    for layer in layers:
        # Empty layers explicitly contribute no override and allow examination of
        # the next lower source without compressing or reinterpreting positions.
        if not layer:
            continue

        matching_components: list[RuntimeComponent] = []
        for component in layer:
            # The callback belongs to fixed Core role-specific logic, not public
            # configuration. Exact booleans prevent truthy component objects or
            # scores from becoming an undocumented ranking or tie-break rule.
            matched = matches(component)
            if type(matched) is not bool:
                raise TypeError("matches must return a boolean.")
            if matched:
                matching_components.append(component)

        # Zero or multiple matches in the highest present layer remain
        # unresolved. Lower layers are never fallbacks once source precedence is
        # fixed, and tuple order or component names cannot break a matching tie.
        if len(matching_components) != 1:
            return None

        component = matching_components[0]
        # Snapshot the exact selected instance and its immutable descriptor. No
        # component method is called, and lower-priority candidates are ignored.
        return SelectedComponent(role, component, component.descriptor)

    # Absence is a valid intermediate selection outcome. The next missing-role
    # branch decides whether the role is required and creates its stable error.
    return None
