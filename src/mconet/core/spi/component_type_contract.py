"""Immutable input and output type ports for one runtime component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi.component_type_port import ComponentTypePort


@dataclass(frozen=True, slots=True)
class ComponentTypeContract:
    """Declare the ordered input and output ports of a component.

    The two directions remain structurally separate so component resolution can
    connect outputs to inputs without encoding direction into each port value.
    Tuple storage preserves declaration order and prevents membership changes.
    Port-name uniqueness and cross-component compatibility are evaluated by the
    resolver that owns the complete connection graph.
    """

    inputs: tuple[ComponentTypePort, ...] = ()
    """Input ports in exact component-declared order."""

    outputs: tuple[ComponentTypePort, ...] = ()
    """Output ports in exact component-declared order."""

    def __post_init__(self) -> None:
        """Require immutable collections containing only component type ports."""
        inputs = cast(object, self.inputs)
        outputs = cast(object, self.outputs)

        # Check each direction independently so a dynamic caller cannot replace
        # immutable port membership with a mutable collection after construction.
        _validate_ports(inputs, "inputs")
        _validate_ports(outputs, "outputs")


def _validate_ports(value: object, field_name: str) -> None:
    """Require one direction to use tuple storage of ComponentTypePort values."""
    # Tuple membership is already immutable, so retaining the original object
    # preserves declaration identity without an unnecessary defensive copy.
    if not isinstance(value, tuple):
        raise TypeError(f"ComponentTypeContract {field_name} must be a tuple.")
    for port in cast(tuple[object, ...], value):
        if not isinstance(port, ComponentTypePort):
            raise TypeError(
                f"ComponentTypeContract {field_name} must contain "
                "ComponentTypePort values."
            )
