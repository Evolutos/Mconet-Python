"""Read-only context observed during interaction capability processing."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import (
    Extensions,
    InteractionMode,
    ModelTarget,
    TaskDescriptor,
)
from mconet.core.spi.component_selection_resolution import (
    ComponentSelectionResolution,
)
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan


@runtime_checkable
class CapabilityContext(Protocol):
    """Expose the fixed interaction facts available to capability processing.

    Collectors, providers, and the deterministic resolver observe the same target,
    task, interaction mode, protocol plan, and already-selected component snapshot.
    The context is read-only and contains no candidate registry, unselected
    components, mutable client configuration, network operations, or resolution
    output that could make capability evaluation depend on hidden global state.
    """

    @property
    def target(self) -> ModelTarget:
        """Return the exact model target for the current interaction."""
        # Capability processing observes validated target identity without
        # resolving another integration, endpoint, credential, or model fallback.
        ...

    @property
    def task(self) -> TaskDescriptor:
        """Return the exact task descriptor for the current interaction."""
        # The descriptor supplies open task identity and schema facts; collectors
        # receive task documents separately as their explicit source values.
        ...

    @property
    def interaction_mode(self) -> InteractionMode:
        """Return the execution mode selected by the public interaction entry point."""
        # Mode is an observed open identity and cannot be changed by capability
        # matching, provider declarations, or compatibility diagnostics.
        ...

    @property
    def execution_plan(self) -> ProtocolExecutionPlan:
        """Return the side-effect-free protocol execution plan."""
        # The plan is produced before capability processing and contains declared
        # requirements only; observing it must not prepare payloads or perform I/O.
        ...

    @property
    def selected_components(self) -> ComponentSelectionResolution:
        """Return the current interaction's uniquely selected component snapshot."""
        # Only components already fixed by deterministic resolution are visible;
        # candidates and unselected defaults cannot contribute capabilities.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return portable versioned context fields for forward compatibility."""
        # Extensions preserve explicit local context facts without becoming an
        # untyped component map, registry, or alternate resolver input channel.
        ...
