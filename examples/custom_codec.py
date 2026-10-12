"""Replace the encoder and the success and error decoders independently."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType

from examples.custom_adapter import CustomTaskAdapter
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
    ComponentTypePort,
    ErasedRuntimeValue,
    InteractionOptions,
    ModelClientConfiguration,
    RuntimeComponents,
    TransportBody,
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
    """Application target for the codec example."""

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


def _json_contract(*, output: bool) -> ComponentTypeContract:
    """Return the JSON port used by the example codecs."""
    port = ComponentTypePort(
        "output" if output else "input",
        OpenIdentifier("json.value"),
        None,
        MediaType("application", "json"),
    )
    if output:
        return ComponentTypeContract(outputs=(port,))
    return ComponentTypeContract(inputs=(port,))


class CountingEncoder:
    """Encoder that counts calls and writes an empty JSON object."""

    def __init__(self) -> None:
        """Store the JSON input contract and a call count."""
        self.descriptor = ComponentDescriptor(
            "counting-encoder",
            "1.0.0",
            "application",
            _json_contract(output=False),
        )
        self.calls = 0

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Count the call and return an empty JSON body."""
        del payload
        self.calls += 1
        return TransportBody(Bytes(b"{}"), MediaType("application", "json"))


class CountingDecoder:
    """Decoder that counts calls and returns one JSON object."""

    def __init__(self, name: str) -> None:
        """Store the decoder name, JSON output contract, and call count."""
        self.descriptor = ComponentDescriptor(
            name,
            "1.0.0",
            "application",
            _json_contract(output=True),
        )
        self.calls = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Count the call and return a JSON object."""
        del raw_data
        self.calls += 1
        return ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": True})


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


async def run_custom_codecs() -> tuple[int, int, int, int]:
    """Run one client call and one call that replaces only the success decoder.

    Returns:
        Client encoder calls, client success-decoder calls, client
        error-decoder calls, and the replacement success-decoder calls.
    """
    encoder = CountingEncoder()
    success = CountingDecoder("counting-success-decoder")
    error = CountingDecoder("counting-error-decoder")
    replacement = CountingDecoder("replacement-success-decoder")
    target: ModelTarget = _ChatTarget(
        OpenIdentifier("service.example"),
        OpenIdentifier("protocol.example"),
        NamedModel("example-model"),
    )
    access: ServiceAccess = _ChatAccess(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    client = ModelClient(
        ModelClientConfiguration(
            components=RuntimeComponents(
                task_protocol_adapter=CustomTaskAdapter(),
                payload_encoder=encoder,
                success_payload_decoder=success,
                error_payload_decoder=error,
                transport=_LocalTransport(),
                authorization_handlers=(NoAuthorizationHandler(),),
            )
        )
    )
    request = model_request_from_text(target, "Hello", access)
    try:
        await client.interact(request, InteractionOptions())
        await client.interact(
            request,
            InteractionOptions(
                components=RuntimeComponents(success_payload_decoder=replacement)
            ),
        )
    finally:
        await client.close()
    return encoder.calls, success.calls, error.calls, replacement.calls
