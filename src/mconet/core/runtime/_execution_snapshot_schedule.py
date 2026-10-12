"""Runtime scheduling that freezes one interaction execution snapshot."""

from __future__ import annotations

from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._capability_validation_schedule import (
    validate_selected_capabilities,
)
from mconet.core.runtime._interaction_execution_components_factory import (
    create_interaction_execution_components,
)
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.capability_requirement import CapabilityRequirement
from mconet.core.spi.component_selection_resolution import (
    ComponentSelectionResolution,
)
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.service_access_resolver import ServiceAccessResolver


def freeze_interaction_execution_components(
    *,
    integration_plan: ModelIntegrationPlan,
    component_selection: ComponentSelectionResolution,
    resource_limits: ResolvedInteractionResourceLimits,
    service_access_resolver: ServiceAccessResolver,
    authorization_handler_resolver: AuthorizationHandlerResolver,
    authorization_handlers: tuple[AuthorizationHandler, ...],
    requirements: tuple[CapabilityRequirement, ...],
) -> InteractionExecutionComponents:
    """Freeze the execution snapshot after type and capability checks.

    A type-contract mismatch or an unsupported required capability raises
    before the snapshot exists. The returned value stores the selected
    instances and completed resolutions. It does not look components up again,
    so a later change to a client collection cannot replace them.

    Args:
        integration_plan: Integration plan whose adapter was selected.
        component_selection: Unique components chosen for this interaction.
        resource_limits: Finite limits already resolved for it.
        service_access_resolver: Resolver retained for later access resolution.
        authorization_handler_resolver: Resolver retained for later handlers.
        authorization_handlers: Ordered handler candidates retained as a tuple.
        requirements: Capability requirements already collected for it.

    Returns:
        The frozen component snapshot for this interaction.

    Raises:
        TypeError: If a completed input has an invalid runtime type.
        ValueError: If limits or the selected role set cannot be retained.
        ModelInteractionError: If adjacent type ports do not connect, or a
            required capability is unsupported.
    """
    # Both gates run before construction. The factory preserves objects; it
    # does not repeat port or capability matching.
    capability_resolution = validate_selected_capabilities(
        component_selection,
        requirements,
    )
    return create_interaction_execution_components(
        integration_plan=integration_plan,
        component_selection=component_selection,
        resource_limits=resource_limits,
        service_access_resolver=service_access_resolver,
        authorization_handler_resolver=authorization_handler_resolver,
        authorization_handlers=authorization_handlers,
        capability_resolution=capability_resolution,
    )
