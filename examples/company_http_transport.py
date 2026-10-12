"""Inject a business HTTP transport at client scope and for one call."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType

from mconet.auth.basic import NoAuthorization, NoAuthorizationHandler
from mconet.client import ModelClient
from mconet.client.text_request import model_request_from_text
from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import (
    Authorization,
    Bytes,
    Extensions,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    InteractionOptions,
    ModelClientConfiguration,
    RuntimeComponents,
    TransportContext,
    TransportOutcome,
    TransportRequest,
    TransportResponse,
    TransportResponseMetadata,
)
from mconet.integration.openai_compatible import OpenAIChatCompletionsAdapter


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _ChatTarget:
    """Application target for the business-transport example."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _ChatAccess:
    """Application access with no authorization."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class CompanyHttpTransport:
    """Stand-in for a company network library used as the unary transport.

    ``send`` records which instance handled the exchange and returns one
    chat-completions JSON body. A real library would perform the network I/O
    inside ``send``; this example keeps that call local so it can run here.
    """

    def __init__(self, name: str) -> None:
        """Store the instance name and an empty transport contract."""
        self.name = name
        self.sends = 0
        self.descriptor = ComponentDescriptor(
            name,
            "1.0.0",
            "application",
            ComponentTypeContract(),
        )

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record the send and return one successful chat response."""
        del request, context
        self.sends += 1
        body = {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hi"},
                    "finish_reason": "stop",
                }
            ]
        }
        return TransportResponse(
            TransportResponseMetadata(
                TransportOutcome(OpenIdentifier("success")),
                Headers(),
                media_type=MediaType("application", "json"),
            ),
            Bytes(json.dumps(body).encode("utf-8")),
        )

    async def close(self) -> None:
        """Release nothing; the example owns no sockets."""
        return None


def _components(transport: CompanyHttpTransport) -> RuntimeComponents:
    """Build the public stack with one business transport."""
    return RuntimeComponents(
        task_protocol_adapter=OpenAIChatCompletionsAdapter(),
        payload_encoder=JsonPayloadEncoder(),
        success_payload_decoder=JsonSuccessPayloadDecoder(1024),
        error_payload_decoder=JsonErrorPayloadDecoder(1024),
        transport=transport,
        authorization_handlers=(NoAuthorizationHandler(),),
    )


async def run_company_transport_injections() -> tuple[str, str]:
    """Use the company transport as the client default and as one call override.

    Returns:
        The transport name that sent the client-level call, then the name that
        sent the per-call override.
    """
    target: ModelTarget = _ChatTarget(
        OpenIdentifier("service.example"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("example-model"),
    )
    access: ServiceAccess = _ChatAccess(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    client_transport = CompanyHttpTransport("client")
    call_transport = CompanyHttpTransport("call")
    client = ModelClient(
        ModelClientConfiguration(
            components=_components(client_transport),
            default_service_access=access,
        )
    )
    request = model_request_from_text(target, "Hello", access)
    try:
        await client.interact(request, InteractionOptions())
        await client.interact(
            request,
            InteractionOptions(
                components=RuntimeComponents(transport=call_transport),
            ),
        )
    finally:
        await client.close()
    stored = client.configuration.components
    assert stored is not None
    assert stored.transport is client_transport
    return client_transport.name, call_transport.name
