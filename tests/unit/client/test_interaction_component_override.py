"""Interaction components outrank client components and are not stored."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from types import MappingProxyType

from mconet.auth.basic import NoAuthorization
from mconet.client._openai_compatible_binding import (
    OPENAI_COMPATIBLE_TYPE_KEY,
    openai_compatible_binding,
)
from mconet.client.model_client import ModelClient
from mconet.client.text_request import model_request_from_text
from mconet.core.domain import (
    Authorization,
    Bytes,
    Extensions,
    HeaderField,
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
from mconet.core.runtime._integration_responsibility_chain import (
    IntegrationResponsibilityChain,
)
from mconet.core.runtime._integration_type_table import IntegrationTypeTable
from mconet.core.runtime.default_model_integration_resolver import (
    DefaultModelIntegrationResolver,
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
)
from mconet.testing import MockHttpResponseScript, MockHttpServer


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural chat-completions target."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Explicit endpoint and no-authorization decision."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _NamedEncoder:
    """Encoder that returns its own body and counts calls."""

    def __init__(self, name: str, body: bytes) -> None:
        """Store the diagnostic name, body, and call count."""
        json_type = OpenIdentifier("json.value")
        media = MediaType("application", "json")
        self.descriptor = ComponentDescriptor(
            name,
            "1.0.0",
            "application",
            ComponentTypeContract(
                inputs=(ComponentTypePort("input", json_type, None, media),)
            ),
        )
        self._body = body
        self.calls = 0

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record the call and return this encoder's body."""
        del payload
        self.calls += 1
        return TransportBody(Bytes(self._body), MediaType("application", "json"))


def test_interaction_encoder_overrides_the_client_without_writing_back() -> None:
    """Verify one call uses the interaction encoder and leaves the client unchanged."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )
    client_encoder = _NamedEncoder("client-encoder", b"from-client")
    interaction_encoder = _NamedEncoder("interaction-encoder", b"from-interaction")
    binding = openai_compatible_binding(max_response_body_bytes=1024)
    resolver = DefaultModelIntegrationResolver(
        IntegrationTypeTable(((OPENAI_COMPATIBLE_TYPE_KEY, binding),)),
        IntegrationResponsibilityChain(()),
    )
    response = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ]
    }
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=json.dumps(response).encode("utf-8"),
    )
    with MockHttpServer((script,)) as server:
        access: ServiceAccess = _Access(server.uri, NoAuthorization())
        configuration = ModelClientConfiguration(
            default_service_access=access,
            components=RuntimeComponents(
                model_integration_resolver=resolver,
                payload_encoder=client_encoder,
            ),
        )
        client = ModelClient(configuration)
        asyncio.run(
            client.interact(
                model_request_from_text(target, "Hello"),
                InteractionOptions(
                    components=RuntimeComponents(
                        payload_encoder=interaction_encoder,
                    )
                ),
            )
        )
        recorded = server.requests

    assert interaction_encoder.calls == 1
    assert client_encoder.calls == 0
    assert recorded[0].body == b"from-interaction"
    assert client.configuration is configuration
    stored = client.configuration.components
    assert stored is not None
    assert stored.payload_encoder is client_encoder
