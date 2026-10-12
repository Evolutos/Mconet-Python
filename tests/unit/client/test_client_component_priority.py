"""Client components are the second component-selection layer."""

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
from mconet.codec.json import JsonErrorPayloadDecoder, JsonSuccessPayloadDecoder
from mconet.core.domain import (
    Authorization,
    Bytes,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
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
from mconet.core.runtime.default_service_access_resolver import (
    DefaultServiceAccessResolver,
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
from mconet.integration.openai_compatible import OpenAIChatCompletionsAdapter
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


class _ClientEncoder:
    """Encoder injected on the client, above the binding encoder."""

    def __init__(self) -> None:
        """Store a JSON input contract and a call count."""
        json_type = OpenIdentifier("json.value")
        media = MediaType("application", "json")
        self.descriptor = ComponentDescriptor(
            "client-encoder",
            "1.0.0",
            "application",
            ComponentTypeContract(
                inputs=(ComponentTypePort("input", json_type, None, media),)
            ),
        )
        self.calls = 0

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record the call and return a body the binding encoder would not."""
        del payload
        self.calls += 1
        return TransportBody(Bytes(b"from-client"), MediaType("application", "json"))


def test_client_encoder_precedes_the_binding_encoder() -> None:
    """Verify a client component is selected before the binding's component."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )
    encoder = _ClientEncoder()
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
        client = ModelClient(
            ModelClientConfiguration(
                default_service_access=access,
                components=RuntimeComponents(
                    model_integration_resolver=resolver,
                    payload_encoder=encoder,
                ),
            )
        )
        asyncio.run(
            client.interact(
                model_request_from_text(target, "Hello"),
                InteractionOptions(),
            )
        )
        recorded = server.requests

    assert encoder.calls == 1
    assert recorded[0].body == b"from-client"
    stored = client.configuration.components
    assert stored is not None
    assert stored.payload_encoder is encoder


class _RecordingTransport:
    """Client transport that records the encoded body and returns one chat JSON."""

    def __init__(self) -> None:
        """Store an empty contract and the bodies this instance was asked to send."""
        self.descriptor = ComponentDescriptor(
            "client-transport",
            "1.0.0",
            "application",
            ComponentTypeContract(),
        )
        self.bodies: list[bytes] = []

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record the body and return a successful chat-completions payload."""
        del context
        self.bodies.append(request.body.bytes)
        payload = {
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
                Headers((HeaderField("Content-Type", "application/json"),)),
                media_type=MediaType("application", "json"),
            ),
            Bytes(json.dumps(payload).encode("utf-8")),
        )


class _CountingDecoder:
    """Decoder that keeps a JSON contract and counts decode calls."""

    def __init__(
        self, inner: JsonSuccessPayloadDecoder | JsonErrorPayloadDecoder
    ) -> None:
        """Copy the inner decoder's contract and start the call count at zero."""
        self.descriptor = inner.descriptor
        self._inner = inner
        self.calls = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record the call and return the inner decoder's payload."""
        self.calls += 1
        return self._inner.decode(raw_data)


class _CountingAccessResolver:
    """Access resolver that counts calls and delegates the field merge."""

    def __init__(self) -> None:
        """Store the builtin resolver, its descriptor, and a call count."""
        inner = DefaultServiceAccessResolver()
        self.descriptor = inner.descriptor
        self._inner = inner
        self.calls = 0

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Record the call and return the builtin merge."""
        self.calls += 1
        return self._inner.resolve(
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )


class _IncompatibleEncoder:
    """Encoder whose contract cannot connect to the JSON adapter output."""

    def __init__(self) -> None:
        """Store a text input contract and a call count."""
        self.descriptor = ComponentDescriptor(
            "bad-encoder",
            "1.0.0",
            "application",
            ComponentTypeContract(
                inputs=(
                    ComponentTypePort(
                        "input",
                        OpenIdentifier("text.plain"),
                        None,
                        MediaType("text", "plain"),
                    ),
                )
            ),
        )
        self.calls = 0

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record a call that selection must not make."""
        del payload
        self.calls += 1
        return TransportBody(Bytes(b"from-client"), MediaType("text", "plain"))


def _chat_target() -> ModelTarget:
    """Return one chat-completions target."""
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )


def test_client_transport_uses_the_sdk_json_codec() -> None:
    """Verify an injected transport leaves encoding and decoding to SDK defaults."""
    transport = _RecordingTransport()
    access: ServiceAccess = _Access(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    client = ModelClient(
        ModelClientConfiguration(
            default_service_access=access,
            components=RuntimeComponents(
                task_protocol_adapter=OpenAIChatCompletionsAdapter(),
                transport=transport,
            ),
        )
    )
    asyncio.run(
        client.interact(
            model_request_from_text(_chat_target(), "Hello"),
            InteractionOptions(),
        )
    )
    assert len(transport.bodies) == 1
    assert b"Hello" in transport.bodies[0]
    stored = client.configuration.components
    assert stored is not None
    assert stored.transport is transport
    assert stored.payload_encoder is None
    assert stored.success_payload_decoder is None


def test_client_codec_and_resolver_precede_the_binding() -> None:
    """Verify client codec, transport, and access resolver beat the binding."""
    encoder = _ClientEncoder()
    success = _CountingDecoder(JsonSuccessPayloadDecoder(1024))
    failure = _CountingDecoder(JsonErrorPayloadDecoder(1024))
    transport = _RecordingTransport()
    access_resolver = _CountingAccessResolver()
    binding = openai_compatible_binding(max_response_body_bytes=1024)
    resolver = DefaultModelIntegrationResolver(
        IntegrationTypeTable(((OPENAI_COMPATIBLE_TYPE_KEY, binding),)),
        IntegrationResponsibilityChain(()),
    )
    access: ServiceAccess = _Access(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    client = ModelClient(
        ModelClientConfiguration(
            default_service_access=access,
            components=RuntimeComponents(
                model_integration_resolver=resolver,
                service_access_resolver=access_resolver,
                payload_encoder=encoder,
                success_payload_decoder=success,
                error_payload_decoder=failure,
                transport=transport,
            ),
        )
    )
    asyncio.run(
        client.interact(
            model_request_from_text(_chat_target(), "Hello"),
            InteractionOptions(),
        )
    )
    assert encoder.calls == 1
    assert success.calls == 1
    assert transport.bodies == [b"from-client"]
    assert access_resolver.calls == 1
    stored = client.configuration.components
    assert stored is not None
    assert stored.transport is transport
    assert stored.payload_encoder is encoder


def test_incompatible_client_encoder_does_not_fall_back_to_the_binding() -> None:
    """Verify a bad client encoder fails before the binding encoder can send."""
    encoder = _IncompatibleEncoder()
    binding = openai_compatible_binding(max_response_body_bytes=1024)
    resolver = DefaultModelIntegrationResolver(
        IntegrationTypeTable(((OPENAI_COMPATIBLE_TYPE_KEY, binding),)),
        IntegrationResponsibilityChain(()),
    )
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=b"{}",
    )
    with MockHttpServer((script,)) as server:
        access: ServiceAccess = _Access(server.uri, NoAuthorization())
        client = ModelClient(
            ModelClientConfiguration(
                default_service_access=access,
                components=RuntimeComponents(
                    model_integration_resolver=resolver,
                    payload_encoder=encoder,
                ),
            )
        )
        try:
            asyncio.run(
                client.interact(
                    model_request_from_text(_chat_target(), "Hello"),
                    InteractionOptions(),
                )
            )
        except ModelInteractionError as error:
            assert error.code == "invalid_component_type_contract"
        else:
            raise AssertionError("Expected the client encoder to fail closed.")
        assert encoder.calls == 0
        assert server.requests == ()
