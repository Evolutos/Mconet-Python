"""Runtime branch for the default model integration resolver."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.model_request import ModelRequest
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver


def resolve_integration_binding(
    resolver: ModelIntegrationResolver,
    request: ModelRequest,
    mode: InteractionMode,
    policy: CompatibilityPolicy,
) -> ModelIntegrationPlan:
    """Form the resolved integration plan from the default resolver.

    This branch has no adapter argument. It cannot turn the request into a
    direct plan. The resolver receives the request target, task descriptor,
    mode, and policy, and its plan is returned unchanged.

    Args:
        resolver: Resolver selected for this interaction.
        request: Validated model request. Only its target and task descriptor
            are read.
        mode: Interaction mode selected by the public entry.
        policy: Compatibility policy already resolved for this interaction.

    Returns:
        The plan returned by ``resolver``.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If the resolver rejects or cannot choose an
            integration.
    """
    resolver_value = cast(object, resolver)
    request_value = cast(object, request)
    mode_value = cast(object, mode)
    policy_value = cast(object, policy)
    if not isinstance(resolver_value, ModelIntegrationResolver):
        raise TypeError("resolver must implement ModelIntegrationResolver.")
    if not isinstance(request_value, ModelRequest):
        raise TypeError("request must implement ModelRequest.")
    if not isinstance(mode_value, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")
    if not isinstance(policy_value, CompatibilityPolicy):
        raise TypeError("policy must be a CompatibilityPolicy.")
    # The resolver is the only decision. This branch does not call supports on
    # an injected adapter and does not invent a direct plan when resolve fails.
    return resolver_value.resolve(
        request_value.target,
        request_value.task.descriptor,
        mode_value,
        policy_value,
    )
