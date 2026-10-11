"""Single runtime join for the direct and resolved integration branches."""

from __future__ import annotations

from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.model_request import ModelRequest
from mconet.core.runtime._direct_adapter_branch import resolve_direct_adapter
from mconet.core.runtime._integration_resolver_branch import (
    resolve_integration_binding,
)
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter


def resolve_model_integration(
    direct_adapter: TaskProtocolAdapter | None,
    resolver: ModelIntegrationResolver,
    request: ModelRequest,
    mode: InteractionMode,
    policy: CompatibilityPolicy,
) -> ModelIntegrationPlan:
    """Choose one integration plan and leave only that plan for later stages.

    An explicit adapter takes the direct branch and the resolver is not called.
    Without an adapter, the resolver branch produces the plan. Both branches
    return one ``ModelIntegrationPlan``. Later runtime stages read that plan
    and do not decide between the branches again.

    Args:
        direct_adapter: Adapter injected for this interaction, or None.
        resolver: Resolver used only when no adapter is injected.
        request: Validated model request.
        mode: Interaction mode selected by the public entry.
        policy: Compatibility policy read only by the resolver branch.

    Returns:
        The one plan selected for this interaction.

    Raises:
        TypeError: If a supplied adapter, resolver, request, mode, or policy
            has an invalid type.
        ModelInteractionError: If the selected branch rejects the request.
    """
    # Presence of the adapter, not its supports result, selects the branch.
    # A rejecting adapter fails inside the direct branch and does not continue
    # to the resolver.
    if direct_adapter is not None:
        return resolve_direct_adapter(direct_adapter, request, mode)
    return resolve_integration_binding(resolver, request, mode, policy)
