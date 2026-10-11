"""Runtime scheduling for one side-effect-free protocol execution plan."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.resolved_service_access import ResolvedServiceAccess
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter


def prepare_protocol_execution_plan(
    request: ModelRequest,
    access: ResolvedServiceAccess,
    mode: InteractionMode,
    plan: ModelIntegrationPlan,
) -> ProtocolExecutionPlan:
    """Ask the selected adapter for one execution plan.

    The adapter is the one already fixed on the integration plan. ``prepare_plan``
    is called once. This stage does not encode the request, read a credential,
    authorize, or send it. A planning failure is returned as raised and is not
    retried.

    Args:
        request: Validated model request being planned.
        access: Resolved non-secret access for this interaction.
        mode: Interaction mode selected by the public entry.
        plan: The one integration plan whose adapter performs planning.

    Returns:
        The execution plan returned by that single ``prepare_plan`` call.

    Raises:
        TypeError: If an argument, or the plan's adapter, has an invalid type.
        ModelInteractionError: If the adapter rejects planning.
    """
    request_value = cast(object, request)
    access_value = cast(object, access)
    mode_value = cast(object, mode)
    plan_value = cast(object, plan)
    if not isinstance(request_value, ModelRequest):
        raise TypeError("request must implement ModelRequest.")
    if not isinstance(access_value, ResolvedServiceAccess):
        raise TypeError("access must be a ResolvedServiceAccess.")
    if not isinstance(mode_value, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")
    if not isinstance(plan_value, ModelIntegrationPlan):
        raise TypeError("plan must be a ModelIntegrationPlan.")

    adapter = plan_value.task_protocol_adapter
    # The plan stores the adapter as a runtime component. Planning requires the
    # task-protocol behavior, and a different component cannot be substituted.
    if not isinstance(adapter, TaskProtocolAdapter):
        raise TypeError("integration plan adapter must implement TaskProtocolAdapter.")
    # One call fixes the plan for this interaction. Encoding, authorization,
    # and transport remain later stages and are not invoked here.
    return adapter.prepare_plan(request_value, access_value, mode_value)
