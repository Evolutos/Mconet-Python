"""Read a bearer credential again on every interaction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType

from examples.custom_adapter import CustomTaskAdapter
from examples.custom_codec import CountingDecoder, CountingEncoder
from mconet.auth.basic import (
    BearerAuthorization,
    BearerAuthorizationHandler,
    DynamicCredentialSource,
)
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
    SecretValue,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import (
    AuthorizationContext,
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
    """Application target for the credential example."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _ChatAccess:
    """Application access whose authorization is supplied by the caller."""

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


class _FreshCredential:
    """Count provider calls and return a new non-secret marker each time."""

    def __init__(self) -> None:
        """Start with no reads."""
        self.reads = 0

    async def __call__(self, context: AuthorizationContext) -> SecretValue:
        """Return a new marker for this interaction."""
        del context
        self.reads += 1
        return SecretValue(str(self.reads))


async def run_dynamic_credential() -> int:
    """Perform two interactions and return how many times the provider ran.

    The provider is not given a fixed credential. Each interaction asks it
    again, including when one interaction asks more than once. The example
    source contains no credential literal.
    """
    provider = _FreshCredential()
    access: ServiceAccess = _ChatAccess(
        UriValue("https://example.test/v1", True),
        BearerAuthorization(DynamicCredentialSource(provider)),
    )
    target: ModelTarget = _ChatTarget(
        OpenIdentifier("service.example"),
        OpenIdentifier("protocol.example"),
        NamedModel("example-model"),
    )
    client = ModelClient(
        ModelClientConfiguration(
            components=RuntimeComponents(
                task_protocol_adapter=CustomTaskAdapter(),
                payload_encoder=CountingEncoder(),
                success_payload_decoder=CountingDecoder("counting-success-decoder"),
                error_payload_decoder=CountingDecoder("counting-error-decoder"),
                transport=_LocalTransport(),
                authorization_handlers=(BearerAuthorizationHandler(),),
            )
        )
    )
    request = model_request_from_text(target, "Hello", access)
    try:
        await client.interact(request, InteractionOptions())
        await client.interact(request, InteractionOptions())
    finally:
        await client.close()
    return provider.reads
