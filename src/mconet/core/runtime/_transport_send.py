"""Runtime scheduling for one unary transport send."""

from __future__ import annotations

from typing import cast

from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.transport import Transport
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_request import TransportRequest
from mconet.core.spi.transport_response import TransportResponse


async def send_interaction_request(
    components: InteractionExecutionComponents,
    request: TransportRequest,
    context: TransportContext,
) -> TransportResponse:
    """Send the frozen request with the interaction's transport context.

    ``send`` is called once on the snapshot's transport. The context is passed
    through unchanged, so its cancellation signal, deadline, and resource
    limits stay the objects already resolved for this interaction. An open
    authorization window is rejected. This stage does not decode the response.

    Args:
        components: Frozen snapshot whose transport performs the send.
        request: Frozen request produced after authorization.
        context: Deadline, cancellation, and limits for this interaction.

    Returns:
        The response returned by that single ``send`` call.

    Raises:
        TypeError: If an argument, the transport, or its result has an invalid
            type, or if the request is still mutable.
    """
    components_value = cast(object, components)
    request_value = cast(object, request)
    context_value = cast(object, context)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if isinstance(request_value, MutableTransportRequest):
        raise TypeError("request must be frozen before transport.")
    if not isinstance(request_value, TransportRequest):
        raise TypeError("request must be a TransportRequest.")
    if not isinstance(context_value, TransportContext):
        raise TypeError("context must be a TransportContext.")

    transport = cast(object, components_value.transport)
    if not isinstance(transport, Transport):
        raise TypeError("transport must implement Transport.")
    response = cast(object, await transport.send(request_value, context_value))
    if not isinstance(response, TransportResponse):
        raise TypeError("transport send must return a TransportResponse.")
    return response
