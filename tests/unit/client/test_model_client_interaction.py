"""ModelClient.interact delegates to the single interaction runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Protocol, cast

from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.auth.basic.no_authorization_handler import NoAuthorizationHandler
from mconet.client.model_client import ModelClient
from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    Bytes,
    ConversationInputNode,
    ConversationTaskBuilder,
    Extensions,
    HeaderField,
    Headers,
    InteractionResourceLimits,
    MediaType,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelDescriptor,
    ModelInteractionError,
    ModelOutput,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskResult,
    MonitoringMergeMode,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    QueryParameters,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TextMessageContent,
    UriValue,
)
from mconet.core.domain.resolved_service_access import ResolvedServiceAccess
from mconet.core.runtime._interaction_runtime import execute_interaction
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningRequirement,
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    InteractionOptions,
    ModelClientConfiguration,
    MonitoringOptions,
    MutableTransportRequest,
    PayloadDecoder,
    PayloadEncoder,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    RawResponseSnapshot,
    RuntimeComponents,
    TaskProtocolAdapter,
    Transport,
    TransportBody,
    TransportContext,
    TransportOutcome,
    TransportRequest,
    TransportRequestPlan,
    TransportResponse,
    TransportResponseMetadata,
    TransportSelection,
)
from mconet.testing import SecretScanner


class _CapturedOutput(Protocol):
    """Assembled output that also carries an opted-in raw response."""

    raw_response: RawResponseSnapshot


def _empty_extensions() -> Extensions:
    """Return one independent empty extension mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target for one conversation request."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for a conversation task root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Container kind for one message group."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Role:
    """User role for one text message."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Request access with an explicit no-authorization decision."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=lambda: MappingProxyType({}))


class _TaskKind:
    """Container kind for one parsed result document."""

    def __init__(self) -> None:
        """Store the kind identity and composition."""
        self.id = OpenIdentifier("task.root")
        self.composition: Literal["container"] = "container"


class _TaskDescriptor:
    """Descriptor for one structural parsed result."""

    def __init__(self) -> None:
        """Store the descriptor fields used by output validation."""
        self.type = OpenIdentifier("vendor.result")
        self.version = "1.0"
        self.input_schema_id = "schema.vendor.input"
        self.output_schema_id = "schema.vendor.output"
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _Result:
    """Structural result retained by the assembled output."""

    def __init__(self) -> None:
        """Store one empty task document."""
        kind: TaskNodeKind = _TaskKind()
        descriptor: TaskDescriptor = _TaskDescriptor()
        self.descriptor = descriptor
        self.document = TaskDocument("1.0", TaskGroupNode("root", kind, ()))
        self.artifacts = ArtifactCatalog()
        self.metadata: Extensions = MappingProxyType({"taskLabel": "vendor.result"})
        self.extensions: Extensions = MappingProxyType({})


class _Pipeline:
    """Record the single runtime call order."""

    def __init__(self) -> None:
        """Start with an empty call list and one shared parsed result."""
        self.calls: list[str] = []
        self.response_headers = Headers()
        self.sent_response: TransportResponse | None = None
        self.result = _Result()
        self.status = OutputStatus(OpenIdentifier("completed"))
        self.parsed = ParsedTaskResponse(
            cast(ModelTaskResult, self.result),
            self.status,
        )


def _port(name: str) -> ComponentTypePort:
    """Build one JSON port used by adjacent component contracts."""
    return ComponentTypePort(
        name,
        OpenIdentifier("json.value"),
        None,
        MediaType("application", "json"),
    )


def _json_contract(
    *,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
) -> ComponentTypeContract:
    """Build a contract whose ports share the JSON value type."""
    return ComponentTypeContract(
        inputs=tuple(_port(name) for name in inputs),
        outputs=tuple(_port(name) for name in outputs),
    )


class _Adapter:
    """Adapter that plans and parses without leaving the success chain."""

    def __init__(self, pipeline: _Pipeline, endpoint: UriValue) -> None:
        """Store the recorder, endpoint, and connecting type contract."""
        self.descriptor = ComponentDescriptor(
            "adapter",
            "1.0.0",
            "application",
            _json_contract(inputs=("response", "error"), outputs=("payload",)),
        )
        self._pipeline = pipeline
        self._endpoint = endpoint

    def supports(self, target: object, task: object, mode: object) -> bool:
        """Accept the injected request without calling another resolver."""
        del target, task, mode
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: object,
    ) -> ProtocolExecutionPlan:
        """Return one unary JSON HTTP plan and record the planning call."""
        del request, mode
        self._pipeline.calls.append("prepare")
        endpoint = access.endpoint if access.endpoint is not None else self._endpoint
        json_type = MediaType("application", "json")
        return ProtocolExecutionPlan(
            TransportRequestPlan(
                endpoint,
                "",
                "POST",
                Headers(),
                QueryParameters(),
                access.authorization,
                BodySigningRequirement(),
            ),
            EncoderSelection(json_type),
            DecoderSelection(json_type),
            DecoderSelection(json_type),
            TransportSelection(OpenIdentifier("http")),
        )

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Record request building and return an empty JSON payload."""
        del request
        self._pipeline.calls.append("build")
        return ProtocolRequestPlan(
            ErasedRuntimeValue(OpenIdentifier("json.value"), {}),
            plan,
        )

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Record parsing and return the shared parsed result."""
        del response
        self._pipeline.calls.append("parse")
        return self._pipeline.parsed

    def parse_error(self, error: object, metadata: object) -> None:
        """Refuse to parse an error on the success path."""
        del error, metadata
        self._pipeline.calls.append("parse-error")
        return None


class _Encoder:
    """Encoder that records one call and returns an empty JSON body."""

    def __init__(self, pipeline: _Pipeline) -> None:
        """Store the recorder and the encoder input contract."""
        self.descriptor = ComponentDescriptor(
            "encoder",
            "1.0.0",
            "application",
            _json_contract(inputs=("input",)),
        )
        self._pipeline = pipeline

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record encoding and return a JSON body."""
        del payload
        self._pipeline.calls.append("encode")
        return TransportBody(Bytes(b"{}"), MediaType("application", "json"))


class _Decoder:
    """Decoder that records its role and returns one JSON object."""

    def __init__(self, pipeline: _Pipeline, label: str) -> None:
        """Store the recorder, role label, and output contract."""
        self.descriptor = ComponentDescriptor(
            label,
            "1.0.0",
            "application",
            _json_contract(outputs=("output",)),
        )
        self._pipeline = pipeline
        self._label = label

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record this decoder and return a JSON value."""
        del raw_data
        self._pipeline.calls.append(self._label)
        return ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": True})


class _RecordedHandler:
    """No-authorization handler that records the apply call."""

    def __init__(self, pipeline: _Pipeline) -> None:
        """Store the recorder and delegate matching to the builtin handler."""
        self._pipeline = pipeline
        self._handler = NoAuthorizationHandler()
        self.descriptor = self._handler.descriptor

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[str]:
        """Return the builtin handler's supported modes."""
        return self._handler.supports(authorization, body_signing_requirement)

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Record application and leave the request unchanged."""
        self._pipeline.calls.append("authorize")
        await self._handler.apply(authorization, context, request)


class _Transport:
    """Transport that records one send and returns a JSON success body."""

    def __init__(self, pipeline: _Pipeline) -> None:
        """Store the recorder and an empty transport contract."""
        self.descriptor = ComponentDescriptor(
            "transport",
            "1.0.0",
            "application",
            ComponentTypeContract(),
        )
        self._pipeline = pipeline

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record the send and return one successful JSON response."""
        del request, context
        self._pipeline.calls.append("send")
        response = TransportResponse(
            TransportResponseMetadata(
                TransportOutcome(OpenIdentifier("success")),
                self._pipeline.response_headers,
                media_type=MediaType("application", "json"),
            ),
            Bytes(b"{}"),
        )
        self._pipeline.sent_response = response
        return response


def _request(service_id: str = "service.vendor") -> ModelRequest:
    """Build one valid unary conversation request with explicit access."""
    role: MessageRole = _Role(OpenIdentifier("message.user"))
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    entry = MessageEntry(
        "message-entry",
        role,
        (TextMessageContent("text-content", "Hello"),),
    )
    messages = MessageDocument(
        "1.0",
        "input",
        MessageGroup("message-root", kind, (entry,)),
    )
    document = TaskDocument(
        "1.0",
        TaskGroupNode(
            "root",
            _NodeKind(OpenIdentifier("task.root"), "container"),
            (ConversationInputNode("input", messages),),
        ),
    )
    task = ConversationTaskBuilder(document).build()
    target: ModelTarget = _Target(
        OpenIdentifier(service_id),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    access: ServiceAccess = _Access(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    return ModelRequestBuilder(target, task).with_service_access(access).build()


class _OrderMonitor:
    """Monitor that records its name when an event is published."""

    def __init__(self, name: str, order: list[str]) -> None:
        """Store the name, shared order list, and an empty descriptor."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application")
        self.observed_events = None
        self._name = name
        self._order = order

    async def on_event(self, event: object) -> None:
        """Append this monitor's name without reading the event body."""
        del event
        self._order.append(self._name)


def _client(
    pipeline: _Pipeline,
    monitoring_defaults: MonitoringOptions | None = None,
) -> tuple[ModelClient, ModelClientConfiguration]:
    """Build a client whose injected components can complete one interaction."""
    endpoint = UriValue("https://example.test/v1", True)
    components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _Adapter(pipeline, endpoint)),
        payload_encoder=cast(PayloadEncoder, _Encoder(pipeline)),
        success_payload_decoder=cast(PayloadDecoder, _Decoder(pipeline, "decode")),
        error_payload_decoder=cast(
            PayloadDecoder,
            _Decoder(pipeline, "error-decode"),
        ),
        transport=cast(Transport, _Transport(pipeline)),
        authorization_handlers=(
            cast(AuthorizationHandler, _RecordedHandler(pipeline)),
        ),
    )
    configuration = ModelClientConfiguration(
        components=components,
        monitoring_defaults=monitoring_defaults,
    )
    return ModelClient(configuration), configuration


def test_interact_delegates_to_the_single_runtime() -> None:
    """Verify interact returns the runtime output and does not store the request."""
    pipeline = _Pipeline()
    client, configuration = _client(pipeline)
    request = _request()
    options = InteractionOptions()

    output = asyncio.run(client.interact(request, options))

    assert pipeline.calls == [
        "prepare",
        "build",
        "encode",
        "authorize",
        "send",
        "decode",
        "parse",
    ]
    assert output.target is request.target
    assert output.status is pipeline.status
    assert output.result is pipeline.result
    assert output.diagnostics == ()
    assert client.configuration is configuration
    assert not hasattr(client, "request")
    direct = asyncio.run(
        execute_interaction(request, options, configuration),
    )
    assert direct.target is output.target
    assert direct.status is output.status
    assert direct.result is output.result


def test_raw_response_is_captured_only_when_requested() -> None:
    """Verify capture is off by default and does not add a decode step."""
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline)
    request = _request()
    plain = asyncio.run(client.interact(request, InteractionOptions()))
    assert not hasattr(plain, "raw_response")
    captured = asyncio.run(
        client.interact(
            request,
            InteractionOptions(include_raw_response=True),
        )
    )
    raw_response = cast(_CapturedOutput, captured).raw_response
    assert raw_response.body == b"{}"
    assert raw_response.metadata.outcome.id.value == "success"
    assert pipeline.calls.count("decode") == 2
    assert pipeline.calls.count("send") == 2


def test_over_limit_raw_response_keeps_metadata_without_the_body() -> None:
    """Verify an over-limit snapshot does not retain the response octets."""
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline)
    captured = asyncio.run(
        client.interact(
            _request(),
            InteractionOptions(
                include_raw_response=True,
                resource_limits=InteractionResourceLimits(
                    max_response_body_bytes=1,
                ),
            ),
        )
    )
    raw_response = cast(_CapturedOutput, captured).raw_response
    assert raw_response.body == b""
    assert raw_response.body_omitted is True
    assert raw_response.metadata.outcome.id.value == "success"
    assert pipeline.calls.count("decode") == 1


def test_raw_response_snapshot_drops_credential_headers() -> None:
    """Verify credential headers and secret names stay off the snapshot."""
    pipeline = _Pipeline()
    pipeline.response_headers = Headers(
        (
            HeaderField("Content-Type", "application/json"),
            HeaderField("Authorization", "mconet-test-bearer-token-not-secret"),
            HeaderField("Proxy-Authorization", "mconet-test-bearer-token-not-secret"),
            HeaderField("Cookie", "session=1"),
            HeaderField("Set-Cookie", "a=b"),
            HeaderField("X-Api-Key", "mconet-test-api-key-not-secret"),
            HeaderField("X-Secret-Value", "mconet-test-signing-secret-not-secret"),
        )
    )
    client, _configuration = _client(pipeline)
    captured = asyncio.run(
        client.interact(
            _request(),
            InteractionOptions(include_raw_response=True),
        )
    )
    raw_response = cast(_CapturedOutput, captured).raw_response
    names = tuple(header.name for header in raw_response.metadata.headers.values)
    assert names == ("Content-Type",)
    scanner = SecretScanner()
    scanner.assert_absent("mconet-test-bearer-token-not-secret", raw_response)
    scanner.assert_absent("mconet-test-api-key-not-secret", raw_response)
    scanner.assert_absent("mconet-test-signing-secret-not-secret", raw_response)
    sent = pipeline.sent_response
    assert sent is not None
    sent_names = tuple(header.name for header in sent.response_metadata.headers.values)
    assert sent_names == (
        "Content-Type",
        "Authorization",
        "Proxy-Authorization",
        "Cookie",
        "Set-Cookie",
        "X-Api-Key",
        "X-Secret-Value",
    )


def _monitoring(name: str, order: list[str], mode: str) -> MonitoringOptions:
    """Return one monitor and an explicit merge mode."""
    return MonitoringOptions(
        monitors=(_OrderMonitor(name, order),),
        merge_mode=MonitoringMergeMode(OpenIdentifier(mode)),
    )


def test_append_publishes_client_monitors_before_interaction_monitors() -> None:
    """Verify append keeps the client monitor ahead of the interaction monitor."""
    order: list[str] = []
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline, _monitoring("client", order, "append"))
    asyncio.run(
        client.interact(
            _request(),
            InteractionOptions(
                monitoring_options=_monitoring("interaction", order, "append")
            ),
        )
    )
    assert order[:2] == ["client", "interaction"]
    assert order == ["client", "interaction"] * (len(order) // 2)


def test_prepend_publishes_interaction_monitors_first() -> None:
    """Verify prepend keeps the interaction monitor ahead of the client monitor."""
    order: list[str] = []
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline, _monitoring("client", order, "append"))
    asyncio.run(
        client.interact(
            _request(),
            InteractionOptions(
                monitoring_options=_monitoring("interaction", order, "prepend")
            ),
        )
    )
    assert order[:2] == ["interaction", "client"]
    assert order == ["interaction", "client"] * (len(order) // 2)


def test_replace_uses_only_interaction_monitors() -> None:
    """Verify an empty replace disables the client monitors."""
    order: list[str] = []
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline, _monitoring("client", order, "append"))
    asyncio.run(
        client.interact(
            _request(),
            InteractionOptions(
                monitoring_options=MonitoringOptions(
                    monitors=(),
                    merge_mode=MonitoringMergeMode(OpenIdentifier("replace")),
                )
            ),
        )
    )
    assert order == []


def test_client_monitors_run_when_the_call_sets_no_merge_mode() -> None:
    """Verify a client replace mode does not erase monitors for an ordinary call."""
    order: list[str] = []
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline, _monitoring("client", order, "replace"))
    asyncio.run(client.interact(_request(), InteractionOptions()))
    assert order
    assert set(order) == {"client"}


def test_unknown_monitoring_merge_mode_fails() -> None:
    """Verify an unknown merge mode is not treated as append."""
    pipeline = _Pipeline()
    client, _configuration = _client(pipeline)
    try:
        asyncio.run(
            client.interact(
                _request(),
                InteractionOptions(
                    monitoring_options=MonitoringOptions(
                        merge_mode=MonitoringMergeMode(OpenIdentifier("shuffle")),
                    )
                ),
            )
        )
    except ModelInteractionError as error:
        assert error.code == "invalid_monitoring_merge_mode"
    else:
        raise AssertionError("Expected an unknown merge mode to fail.")


def test_open_client_accepts_concurrent_interactions() -> None:
    """Verify one open client can run two interactions at the same time."""
    pipeline = _Pipeline()
    client, configuration = _client(pipeline)
    first = _request("service.one")
    second = _request("service.two")

    async def _run_both() -> tuple[ModelOutput, ModelOutput]:
        return await asyncio.gather(
            client.interact(first, InteractionOptions()),
            client.interact(second, InteractionOptions()),
        )

    first_output, second_output = asyncio.run(_run_both())
    assert first_output.target is first.target
    assert second_output.target is second.target
    assert client.configuration is configuration
    later = asyncio.run(client.interact(first, InteractionOptions()))
    assert later.target is first.target
