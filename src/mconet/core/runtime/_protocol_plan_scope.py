"""R1 scope gate for one prepared protocol execution plan."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.media_type import MediaType
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan

_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_PROTOCOL_PLANNING = InteractionPhase(OpenIdentifier("protocol_planning"))
_UNARY_MODE_ID = OpenIdentifier("unary")
_HTTP_TRANSPORT_KIND = OpenIdentifier("http")
_JSON_MEDIA_TYPE = MediaType("application", "json")
_ACCEPTED_PORT_TYPES = frozenset(
    (
        OpenIdentifier("json.value"),
        OpenIdentifier("transport.bytes"),
    )
)
_UNSUPPORTED_MODE_CODE = "unsupported_interaction_mode"
_UNSUPPORTED_PLAN_CODE = "unsupported_protocol_plan"
_UNSUPPORTED_MODE_MESSAGE = "Only unary interaction mode is supported."
_UNSUPPORTED_PLAN_MESSAGE = "Only a unary JSON HTTP bytes execution plan is supported."


def validate_r1_protocol_execution_plan(
    mode: InteractionMode,
    plan: ProtocolExecutionPlan,
) -> ProtocolExecutionPlan:
    """Accept one R1 plan and reject every other execution shape.

    A plan passes when the mode is unary, the plan declares no extra mode
    components, the encoder and both decoders are parameter-free
    ``application/json``, the transport kind is HTTP with no extra
    capabilities, and every type port is ``json.value`` or ``transport.bytes``.
    The first mismatch raises. This gate does not select components or perform
    I/O.

    Args:
        mode: Interaction mode already selected for this interaction.
        plan: Execution plan returned by the single ``prepare_plan`` call.

    Returns:
        The same plan when it is inside the R1 unary JSON HTTP bytes scope.

    Raises:
        TypeError: If ``mode`` or ``plan`` has an invalid runtime type.
        ModelInteractionError: If the mode or plan is outside that scope. A
            non-unary mode uses ``unsupported_interaction_mode``. Any other
            mismatch uses ``unsupported_protocol_plan``.
    """
    mode_value = cast(object, mode)
    plan_value = cast(object, plan)
    if not isinstance(mode_value, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")
    if not isinstance(plan_value, ProtocolExecutionPlan):
        raise TypeError("plan must be a ProtocolExecutionPlan.")

    # Mode is checked before plan fields so a streaming mode fails even when
    # the plan itself still looks like a unary HTTP request.
    if mode_value.id != _UNARY_MODE_ID or plan_value.mode_components:
        raise _scope_error(_UNSUPPORTED_MODE_CODE, _UNSUPPORTED_MODE_MESSAGE)
    _require_json(plan_value.payload_encoder.media_type)
    _require_json(plan_value.success_decoder.media_type)
    _require_json(plan_value.error_decoder.media_type)
    transport = plan_value.transport
    # Extra capabilities would select a streaming or non-HTTP transport. R1
    # accepts only plain HTTP.
    if (
        transport.transport_kind != _HTTP_TRANSPORT_KIND
        or transport.required_capabilities
    ):
        raise _scope_error(_UNSUPPORTED_PLAN_CODE, _UNSUPPORTED_PLAN_MESSAGE)
    _require_r1_ports(plan_value)
    return plan_value


def _require_json(media_type: MediaType | None) -> None:
    """Reject a missing or non-JSON media type."""
    # Parameter-free application/json is the frozen R1 wire type. A +json
    # subtype or a parameter does not enter this release.
    if media_type != _JSON_MEDIA_TYPE:
        raise _scope_error(_UNSUPPORTED_PLAN_CODE, _UNSUPPORTED_PLAN_MESSAGE)


def _require_r1_ports(plan: ProtocolExecutionPlan) -> None:
    """Reject a type port that is neither a JSON value nor transport bytes."""
    ports = (*plan.type_contract.inputs, *plan.type_contract.outputs)
    # The adapter boundary uses json.value. The transport boundary uses
    # transport.bytes. Both encode to the R1 byte body. Any other type does not.
    for port in ports:
        if port.type_id not in _ACCEPTED_PORT_TYPES:
            raise _scope_error(_UNSUPPORTED_PLAN_CODE, _UNSUPPORTED_PLAN_MESSAGE)
        if port.media_type is not None and port.media_type != _JSON_MEDIA_TYPE:
            raise _scope_error(_UNSUPPORTED_PLAN_CODE, _UNSUPPORTED_PLAN_MESSAGE)


def _scope_error(code: str, message: str) -> ModelInteractionError:
    """Create one stable planning-phase failure without request data."""
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE,
        phase=_PROTOCOL_PLANNING,
        code=code,
        message=message,
    )
