"""Tests that transport receives the interaction signal, deadline, and limits."""

from __future__ import annotations

import asyncio
from typing import cast

from mconet.core.domain import (
    Bytes,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    Timestamp,
    UriValue,
)
from mconet.core.runtime._transport_send import send_interaction_request
from mconet.core.spi import (
    AuthorizationHandlerResolver,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentSelectionResolution,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    PayloadDecoder,
    PayloadEncoder,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
    TransportBody,
    TransportContext,
    TransportOutcome,
    TransportRequest,
    TransportResponse,
    TransportResponseMetadata,
)
from mconet.testing import ControllableCancellationSignal


class _Transport:
    """Transport that records the context it was given."""

    def __init__(self, response: TransportResponse) -> None:
        """Store the response and an empty call list."""
        self.descriptor = ComponentDescriptor("transport", "1.0.0", "application")
        self._response = response
        self.contexts: list[TransportContext] = []

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record the context and return the prepared response."""
        del request
        self.contexts.append(context)
        return self._response


def _components(transport: _Transport) -> InteractionExecutionComponents:
    """Store the transport without constructing the other roles."""
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=cast(ResolvedInteractionResourceLimits, unused),
        task_protocol_adapter=cast(TaskProtocolAdapter, unused),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, unused),
        success_payload_decoder=cast(PayloadDecoder, unused),
        error_payload_decoder=cast(PayloadDecoder, unused),
        transport=cast(Transport, transport),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, unused),
        authorization_handlers=(),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def test_send_passes_signal_deadline_and_limits_once() -> None:
    """Verify the transport observes the already resolved context by identity."""
    signal = ControllableCancellationSignal()
    limits = ResolvedInteractionResourceLimits(4_096, 1_024, 512)
    deadline = Timestamp(1_700_000_001, 0)
    context = TransportContext(
        interaction_id="interaction-1",
        resource_limits=limits,
        deadline=deadline,
        cancellation=signal,
    )
    response = TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("success")),
            Headers(),
        ),
        Bytes(b"{}"),
    )
    transport = _Transport(response)
    request = TransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/chat/completions", True),
        headers=Headers(),
        query=QueryParameters(),
        body=TransportBody(Bytes(b"{}"), MediaType("application", "json")),
    )

    sent = asyncio.run(
        send_interaction_request(_components(transport), request, context)
    )

    assert sent is response
    assert transport.contexts == [context]
    assert transport.contexts[0].cancellation is signal
    assert transport.contexts[0].deadline is deadline
    assert transport.contexts[0].resource_limits is limits
