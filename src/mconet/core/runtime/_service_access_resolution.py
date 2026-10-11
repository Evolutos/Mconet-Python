"""Runtime scheduling for one interaction's service access resolution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.resolved_service_access import ResolvedServiceAccess
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.service_access_resolver import ServiceAccessResolver


def resolve_service_access(
    resolver: ServiceAccessResolver,
    request: ModelRequest,
    plan: ModelIntegrationPlan,
    *,
    interaction_layer: InteractionConfigurationLayer,
    client_layer: InteractionConfigurationLayer,
) -> ResolvedServiceAccess:
    """Resolve the four access layers for one interaction.

    The layers stay in resolver order: interaction override, request access,
    client default, then the integration plan's protocol default. This function
    does not merge fields itself and does not copy a result back onto the
    client layer. A resolver failure, including missing authorization, is left
    unchanged so the stable resolution error reaches the caller.

    Args:
        resolver: The access resolver selected for this interaction.
        request: Validated model request. Only its service access is read.
        plan: The one integration plan. Only its default service access is read.
        interaction_layer: Interaction-owned access override, if any.
        client_layer: Reusable client default. This object is not modified.

    Returns:
        The resolver's immutable access snapshot.

    Raises:
        TypeError: If an argument has an invalid runtime type.
        ValueError: If a present access layer is semantically invalid.
        ModelInteractionError: If resolution fails. Missing authorization uses
            code ``missing_authorization`` and phase ``service_access_resolution``.
    """
    resolver_value = cast(object, resolver)
    request_value = cast(object, request)
    plan_value = cast(object, plan)
    interaction_value = cast(object, interaction_layer)
    client_value = cast(object, client_layer)
    if not isinstance(resolver_value, ServiceAccessResolver):
        raise TypeError("resolver must implement ServiceAccessResolver.")
    if not isinstance(request_value, ModelRequest):
        raise TypeError("request must implement ModelRequest.")
    if not isinstance(plan_value, ModelIntegrationPlan):
        raise TypeError("plan must be a ModelIntegrationPlan.")
    if not isinstance(interaction_value, InteractionConfigurationLayer):
        raise TypeError("interaction_layer must be InteractionConfigurationLayer.")
    if not isinstance(client_value, InteractionConfigurationLayer):
        raise TypeError("client_layer must be InteractionConfigurationLayer.")

    # Pass the four original layers. The earlier configuration merge selects one
    # whole access object and must not replace this field-by-field resolution.
    # Nothing here assigns the result, or a layer, back onto the client.
    return resolver_value.resolve(
        interaction_value.service_access,
        request_value.service_access,
        client_value.service_access,
        plan_value.default_service_access,
    )
