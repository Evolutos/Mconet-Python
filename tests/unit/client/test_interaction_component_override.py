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
    InteractionMode,
    MediaType,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    ParsedTaskResponse,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    TaskDescriptor,
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
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
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


class _RecordingTransport:
    """Transport that records sends and returns one chat JSON body."""

    def __init__(self, name: str) -> None:
        """Store the instance name, an empty contract, and a send count."""
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
        """Record the send and return a successful chat-completions payload."""
        del request, context
        self.sends += 1
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


class _CountingAdapter:
    """Adapter that counts prepare calls and delegates the OpenAI mapping."""

    def __init__(self) -> None:
        """Store the OpenAI adapter, its descriptor, and a prepare count."""
        inner = OpenAIChatCompletionsAdapter()
        self.descriptor = inner.descriptor
        self._inner = inner
        self.prepares = 0

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return the inner adapter's applicability."""
        return self._inner.supports(target, task, mode)

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Record the call and return the inner plan."""
        self.prepares += 1
        return self._inner.prepare_plan(request, access, mode)

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return the inner request plan."""
        return self._inner.build_request(request, plan)

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Return the inner parsed success."""
        return self._inner.parse_response(response)

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Return the inner parsed error."""
        return self._inner.parse_error(error, metadata)


def test_interaction_transport_overrides_the_client_without_writing_back() -> None:
    """Verify one call uses another transport and leaves the client transport."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )
    client_transport = _RecordingTransport("client")
    call_transport = _RecordingTransport("call")
    access: ServiceAccess = _Access(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    configuration = ModelClientConfiguration(
        default_service_access=access,
        components=RuntimeComponents(
            task_protocol_adapter=OpenAIChatCompletionsAdapter(),
            transport=client_transport,
        ),
    )
    client = ModelClient(configuration)
    request = model_request_from_text(target, "Hello")
    asyncio.run(
        client.interact(
            request,
            InteractionOptions(
                components=RuntimeComponents(transport=call_transport),
            ),
        )
    )
    assert call_transport.sends == 1
    assert client_transport.sends == 0
    assert client.configuration is configuration
    stored = configuration.components
    assert stored is not None
    assert stored.transport is client_transport
    asyncio.run(client.interact(request, InteractionOptions()))
    assert client_transport.sends == 1
    assert call_transport.sends == 1


def test_interaction_adapter_prepares_the_plan_without_writing_back() -> None:
    """Verify the call adapter plans the request and the client adapter stays idle."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )
    client_adapter = _CountingAdapter()
    call_adapter = _CountingAdapter()
    transport = _RecordingTransport("client")
    access: ServiceAccess = _Access(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    configuration = ModelClientConfiguration(
        default_service_access=access,
        components=RuntimeComponents(
            task_protocol_adapter=client_adapter,
            transport=transport,
        ),
    )
    client = ModelClient(configuration)
    asyncio.run(
        client.interact(
            model_request_from_text(target, "Hello"),
            InteractionOptions(
                components=RuntimeComponents(task_protocol_adapter=call_adapter),
            ),
        )
    )
    assert call_adapter.prepares == 1
    assert client_adapter.prepares == 0
    assert client.configuration is configuration
    stored = configuration.components
    assert stored is not None
    assert stored.task_protocol_adapter is client_adapter
