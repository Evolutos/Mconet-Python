"""Runtime branch for an explicitly injected task protocol adapter."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.model_request import ModelRequest
from mconet.core.runtime._direct_model_integration_plan import (
    direct_model_integration_plan,
)
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter


def resolve_direct_adapter(
    adapter: TaskProtocolAdapter,
    request: ModelRequest,
    mode: InteractionMode,
) -> ModelIntegrationPlan:
    """Form the direct integration plan for one explicit adapter.

    This branch has no resolver argument. An adapter that rejects the request
    fails here, and the failure cannot fall back to a default resolver. The
    plan keeps the injected adapter instance and does not plan, encode, or send.

    Args:
        adapter: Adapter injected for this interaction.
        request: Validated model request. Only its target and task descriptor
            are read.
        mode: Interaction mode selected by the public entry.

    Returns:
        A plan whose source is ``direct_adapter``.

    Raises:
        TypeError: If an argument has an invalid type, or ``supports`` does not
            return a bool.
        ModelInteractionError: If the adapter does not support the request.
    """
    request_value = cast(object, request)
    mode_value = cast(object, mode)
    # The request and mode are the public inputs. The adapter check stays in
    # the direct-plan function so support policy has one implementation.
    if not isinstance(request_value, ModelRequest):
        raise TypeError("request must implement ModelRequest.")
    if not isinstance(mode_value, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")
    # No resolver is in scope. Rejection ends this branch.
    return direct_model_integration_plan(
        adapter,
        request_value.target,
        request_value.task.descriptor,
        mode_value,
    )
