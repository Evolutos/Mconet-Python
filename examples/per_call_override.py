"""Override one component for a single call without changing the client."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType

from examples.custom_adapter import CustomTaskAdapter
from examples.custom_codec import CountingDecoder, CountingEncoder
from mconet.auth.basic import NoAuthorization, NoAuthorizationHandler
from mconet.client import ModelClient
from mconet.client.text_request import model_request_from_text
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


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _ChatTarget:
    """Application target for the override example."""

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


class _LocalTransport:
    """Transport that returns one JSON object without using the network."""

    def __init__(self) -> None:
        """Store an empty transport contract."""
        self.descriptor = ComponentDescriptor(
            "local-transport",
            "1.0.0",
            "application",
            ComponentTypeContract(),
        )

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Return a small JSON success body."""
        del request, context
        return TransportResponse(
            TransportResponseMetadata(
                TransportOutcome(OpenIdentifier("success")),
                Headers(),
                media_type=MediaType("application", "json"),
            ),
            Bytes(json.dumps({"ok": True}).encode("utf-8")),
        )


async def run_per_call_override() -> tuple[bool, int, int]:
    """Replace the encoder for one call and leave the client configuration.

    Returns:
        Whether the configuration object and its encoder are unchanged, the
        client encoder's call count, and the override encoder's call count.
    """
    client_encoder = CountingEncoder()
    override = CountingEncoder()
    target: ModelTarget = _ChatTarget(
        OpenIdentifier("service.example"),
        OpenIdentifier("protocol.example"),
        NamedModel("example-model"),
    )
    access: ServiceAccess = _ChatAccess(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    configuration = ModelClientConfiguration(
        components=RuntimeComponents(
            task_protocol_adapter=CustomTaskAdapter(),
            payload_encoder=client_encoder,
            success_payload_decoder=CountingDecoder("counting-success-decoder"),
            error_payload_decoder=CountingDecoder("counting-error-decoder"),
            transport=_LocalTransport(),
            authorization_handlers=(NoAuthorizationHandler(),),
        )
    )
    client = ModelClient(configuration)
    request = model_request_from_text(target, "Hello", access)
    try:
        await client.interact(
            request,
            InteractionOptions(components=RuntimeComponents(payload_encoder=override)),
        )
    finally:
        await client.close()
    stored = client.configuration.components
    unchanged = (
        client.configuration is configuration
        and stored is not None
        and stored.payload_encoder is client_encoder
    )
    return unchanged, client_encoder.calls, override.calls
