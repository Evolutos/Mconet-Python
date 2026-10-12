"""Runtime scheduling for capability checks after type-contract validation."""

from __future__ import annotations

from mconet.core.runtime._capability_resolution import resolve_capabilities
from mconet.core.runtime._type_contract_validation import (
    validate_selected_type_contracts,
)
from mconet.core.spi.capability_requirement import CapabilityRequirement
from mconet.core.spi.capability_resolution import CapabilityResolution
from mconet.core.spi.component_selection_resolution import ComponentSelectionResolution


def validate_selected_capabilities(
    selection: ComponentSelectionResolution,
    requirements: tuple[CapabilityRequirement, ...],
) -> CapabilityResolution:
    """Validate capabilities only after adjacent type ports connect.

    Type-contract failure stops this stage, so a broken port edge cannot be
    reported as a missing capability. Required capabilities that no selected
    component declares fail the interaction. Optional capabilities that no
    selected component declares stay in the resolution as diagnostics and do
    not fail it. This schedule does not collect requirements, invoke a
    component, or freeze the execution snapshot.

    Args:
        selection: Unique components already chosen for this interaction.
        requirements: Capability requirements already collected for it.

    Returns:
        The capability resolution for those requirements.

    Raises:
        TypeError: If the selection or a requirement has an invalid type.
        ModelInteractionError: If adjacent type ports do not connect, or a
            required capability is unsupported.
    """
    # The type gate returns the same selection or raises. Capability matching
    # therefore never observes a selection that cannot execute.
    checked = validate_selected_type_contracts(selection)
    return resolve_capabilities(requirements, checked)
