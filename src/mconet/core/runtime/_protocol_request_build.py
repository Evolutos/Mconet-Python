"""Runtime scheduling for one protocol request plan."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.model_request import ModelRequest
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan
from mconet.core.spi.protocol_request_plan import ProtocolRequestPlan
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter


def build_protocol_request(
    request: ModelRequest,
    components: InteractionExecutionComponents,
    execution_plan: ProtocolExecutionPlan,
) -> ProtocolRequestPlan:
    """Ask the frozen adapter to map one request into a protocol plan.

    ``build_request`` is called once on the snapshot's adapter. The result is
    a protocol request plan and is not encoded, authorized, or sent. A mapping
    failure is returned as raised and is not retried.

    Args:
        request: Validated model request being mapped.
        components: Frozen snapshot whose adapter performs the mapping.
        execution_plan: Plan already prepared for this interaction.

    Returns:
        The protocol request plan returned by that single ``build_request`` call.

    Raises:
        TypeError: If an argument, the adapter, or its return value has an
            invalid type.
        ModelInteractionError: If the adapter rejects the request.
    """
    request_value = cast(object, request)
    components_value = cast(object, components)
    plan_value = cast(object, execution_plan)
    if not isinstance(request_value, ModelRequest):
        raise TypeError("request must implement ModelRequest.")
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(plan_value, ProtocolExecutionPlan):
        raise TypeError("execution_plan must be a ProtocolExecutionPlan.")

    adapter = cast(object, components_value.task_protocol_adapter)
    # The snapshot already fixed this adapter. A caller-supplied replacement
    # cannot build the request, and a metadata-only component cannot map it.
    if not isinstance(adapter, TaskProtocolAdapter):
        raise TypeError("task_protocol_adapter must implement TaskProtocolAdapter.")
    built = cast(object, adapter.build_request(request_value, plan_value))
    # Encoding consumes this plan later. A value that is not a protocol request
    # plan cannot enter that stage.
    if not isinstance(built, ProtocolRequestPlan):
        raise TypeError("build_request must return a ProtocolRequestPlan.")
    return built
