"""Runtime scheduling for one payload encoding step."""

from __future__ import annotations

from typing import cast

from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.payload_encoder import PayloadEncoder
from mconet.core.spi.protocol_request_plan import ProtocolRequestPlan
from mconet.core.spi.transport_body import TransportBody


def encode_protocol_payload(
    components: InteractionExecutionComponents,
    request_plan: ProtocolRequestPlan,
) -> TransportBody:
    """Encode the protocol payload with the frozen encoder.

    ``encode`` is called once. Authorization handlers are not applied, and
    the body is not sent. An encoding failure is returned as raised and is
    not retried, so the authorization stage does not start.

    Args:
        components: Frozen snapshot whose encoder performs the conversion.
        request_plan: Protocol plan whose payload is encoded.

    Returns:
        The transport body returned by that single ``encode`` call.

    Raises:
        TypeError: If an argument, the encoder, or its return value has an
            invalid type.
        ModelInteractionError: If the encoder rejects the payload.
    """
    components_value = cast(object, components)
    plan_value = cast(object, request_plan)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(plan_value, ProtocolRequestPlan):
        raise TypeError("request_plan must be a ProtocolRequestPlan.")

    encoder = cast(object, components_value.payload_encoder)
    # The snapshot already fixed this encoder. A different encoder cannot
    # replace it after the request plan exists.
    if not isinstance(encoder, PayloadEncoder):
        raise TypeError("payload_encoder must implement PayloadEncoder.")
    encoded = cast(object, encoder.encode(plan_value.payload))
    # Authorization reads this body later. A value that is not a transport
    # body cannot enter that stage.
    if not isinstance(encoded, TransportBody):
        raise TypeError("encode must return a TransportBody.")
    return encoded
