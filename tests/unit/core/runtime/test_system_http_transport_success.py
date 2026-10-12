"""System HTTP success case equivalent to the mock-transport output."""

from __future__ import annotations

import asyncio
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    Bytes,
    CompatibilityPolicy,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelOutput,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    ModelTaskResult,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    Timestamp,
    UriValue,
)
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime._mock_transport_success import run_mock_transport_success
from mconet.core.runtime._response_resource_release import ResponseResources
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    BodySigningRequirement,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentSelectionResolution,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    MonitoringEvent,
    PayloadDecoder,
    PayloadEncoder,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    ResolvedAuthorizationHandler,
    ServiceAccessResolver,
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
from mconet.testing import (
    ComponentCallRecorder,
    MockHttpResponseScript,
    MockHttpServer,
    MockTransport,
    StubInteractionMonitor,
)
from mconet.transport.http_system import DefaultSystemHttpTransport

_RESPONSE_BODY = b'{"ok":true}'
_SUCCESS_CALLS = ("build", "encode", "authorize", "send", "decode", "parse")
_LIMITS = ResolvedInteractionResourceLimits(1024, 1024, 1024)


class _TaskKind:
    """Container kind for one empty task document."""

    def __init__(self) -> None:
        """Store the kind identity and composition."""
        self.id = OpenIdentifier("task.root")
        self.composition: Literal["container"] = "container"


class _TaskDescriptor:
    """Task descriptor for one structural request or result."""

    def __init__(self, task_type: str) -> None:
        """Store the descriptor fields used by output validation."""
        self.type = OpenIdentifier(task_type)
        self.version = "1.0"
        self.input_schema_id = "schema.vendor.input"
        self.output_schema_id = "schema.vendor.output"
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _TaskValue:
    """Structural task value shared by a request and a result."""

    def __init__(self, task_type: str) -> None:
        """Store one empty task document."""
        kind: TaskNodeKind = _TaskKind()
        descriptor: TaskDescriptor = _TaskDescriptor(task_type)
        self.descriptor = descriptor
        self.document = TaskDocument("1.0", TaskGroupNode("root", kind, ()))
        self.artifacts = ArtifactCatalog()
        self.metadata: Extensions = MappingProxyType({"taskLabel": task_type})
        self.extensions: Extensions = MappingProxyType({})


class _Target:
    """Request target retained by the assembled output."""

    def __init__(self) -> None:
        """Store one named model target."""
        self.service_id = OpenIdentifier("service.vendor")
        self.protocol_id = OpenIdentifier("protocol.vendor")
        self.model: ModelDescriptor = NamedModel("requested-model")
        self.deployment_id = "deployment-primary"
        self.extensions: Extensions = MappingProxyType({})


class _Request:
    """Request whose target must remain the output target."""

    def __init__(self, target: ModelTarget) -> None:
        """Store the request around one task."""
        task: ModelTaskRequest = _TaskValue("vendor.request")
        self.target = target
        self.task = task
        self.service_access = None
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _Authorization:
    """Authorization decision with no credential source."""

    def __init__(self) -> None:
        """Store the handler-selection kind."""
        self.kind = OpenIdentifier("authorization.none")


class _Adapter:
    """Adapter that accepts only the scripted success payload."""

    def __init__(
        self,
        recorder: ComponentCallRecorder,
        parsed: ParsedTaskResponse,
        plan: ProtocolExecutionPlan,
    ) -> None:
        """Store the recorder and the shared parsed response."""
        self.descriptor = ComponentDescriptor("adapter", "1.0.0", "application")
        self._recorder = recorder
        self._parsed = parsed
        self._plan = plan

    def supports(self, *values: object) -> bool:
        """Report that this adapter can handle the fixture."""
        del values
        return True

    def prepare_plan(self, *values: object) -> ProtocolExecutionPlan:
        """Return the plan without recording a second planning call."""
        del values
        return self._plan

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Record the request build and return a JSON payload plan."""
        del request
        self._recorder.record("build")
        return ProtocolRequestPlan(
            ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": True}),
            plan,
        )

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Return the shared response only for the scripted success value."""
        self._recorder.record("parse")
        # The output is equivalent only when both transports delivered the same
        # decoded payload. A different body must not reuse this parsed response.
        if response.value != {"ok": True}:
            raise ValueError("The decoded payload is not the scripted success value.")
        return self._parsed

    def parse_error(self, *values: object) -> None:
        """Record an error parse that the success case must not perform."""
        del values
        self._recorder.record("parse-error")
        return None


class _Encoder:
    """Encoder that records one call and returns an empty JSON body."""

    def __init__(self, recorder: ComponentCallRecorder) -> None:
        """Store the shared call recorder."""
        self.descriptor = ComponentDescriptor("encoder", "1.0.0", "application")
        self._recorder = recorder

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record encoding and return a JSON body."""
        del payload
        self._recorder.record("encode")
        return TransportBody(Bytes(b"{}"), MediaType("application", "json"))


class _Decoder:
    """Decoder that accepts only the scripted success body."""

    def __init__(self, recorder: ComponentCallRecorder, label: str) -> None:
        """Store the recorder and the role label."""
        self.descriptor = ComponentDescriptor(label, "1.0.0", "application")
        self._recorder = recorder
        self._label = label

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record this decoder and require the scripted success bytes."""
        self._recorder.record(self._label)
        # The success decoder is the only reader of the network body. Rejecting
        # any other bytes keeps the assembled output tied to that response.
        if self._label == "decode" and raw_data != _RESPONSE_BODY:
            raise ValueError("The response body is not the scripted success payload.")
        return ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": True})


class _Resolver:
    """Resolver that selects the only configured handler."""

    def __init__(self) -> None:
        """Store resolver metadata."""
        self.descriptor = ComponentDescriptor("resolver", "1.0.0", "application")

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> object:
        """Return the first handler in none mode."""
        del authorization, body_signing_requirement
        return ResolvedAuthorizationHandler(handlers[0], "none")


class _Handler:
    """Handler that records authorization and leaves the request unchanged."""

    def __init__(self, recorder: ComponentCallRecorder) -> None:
        """Store the shared call recorder."""
        self.descriptor = ComponentDescriptor("handler", "1.0.0", "application")
        self._recorder = recorder

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[Literal["none"]]:
        """Accept the unsigned mode."""
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: object,
    ) -> None:
        """Record authorization without changing the request."""
        del authorization, context, request
        self._recorder.record("authorize")


class _RecordingTransport:
    """Record one send, then delegate to the supplied transport."""

    def __init__(self, recorder: ComponentCallRecorder, transport: Transport) -> None:
        """Store the recorder and the transport that performs the exchange."""
        self.descriptor = transport.descriptor
        self._recorder = recorder
        self._transport = transport

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record the send stage and return the delegated response."""
        self._recorder.record("send")
        return await self._transport.send(request, context)


def _plan(endpoint: UriValue) -> ProtocolExecutionPlan:
    """Build one unary HTTP plan aimed at the supplied endpoint."""
    return ProtocolExecutionPlan(
        TransportRequestPlan(
            endpoint,
            "",
            "POST",
            Headers(),
            QueryParameters(),
            cast(Authorization, _Authorization()),
            BodySigningRequirement(),
        ),
        EncoderSelection(),
        DecoderSelection(),
        DecoderSelection(),
        TransportSelection(OpenIdentifier("http")),
    )


def _components(
    recorder: ComponentCallRecorder,
    transport: Transport,
    plan: ProtocolExecutionPlan,
    parsed: ParsedTaskResponse,
) -> InteractionExecutionComponents:
    """Freeze one success snapshot around the supplied transport."""
    adapter = _Adapter(recorder, parsed, plan)
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=_LIMITS,
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, _Encoder(recorder)),
        success_payload_decoder=cast(PayloadDecoder, _Decoder(recorder, "decode")),
        error_payload_decoder=cast(PayloadDecoder, _Decoder(recorder, "error-decode")),
        transport=transport,
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, _Resolver()),
        authorization_handlers=(cast(AuthorizationHandler, _Handler(recorder)),),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def _context(request: ModelRequest, target: ModelTarget) -> InteractionContext:
    """Create one interaction context that this run will release."""
    return InteractionContext(
        request,
        ResolvedInteractionConfiguration(
            target,
            None,
            CompatibilityPolicy(OpenIdentifier("strict")),
            _LIMITS,
            None,
        ),
    )


async def _run(
    *,
    request: ModelRequest,
    target: ModelTarget,
    endpoint: UriValue,
    components: InteractionExecutionComponents,
    plan: ProtocolExecutionPlan,
) -> ModelOutput:
    """Run the single success pipeline for one transport snapshot."""
    context = _context(request, target)
    resources = ResponseResources(Bytes(_RESPONSE_BODY), lambda: None)
    monitor = StubInteractionMonitor(
        ComponentDescriptor("monitor", "1.0.0", "application"),
        None,
    )
    completed = MonitoringEvent(
        "event-completed",
        OpenIdentifier("interaction.completed"),
        "interaction-1",
        None,
        Timestamp(1_700_000_000, 0),
        {"status": "completed"},
        {},
    )
    return await run_mock_transport_success(
        request=request,
        components=components,
        execution_plan=plan,
        authorization_context=AuthorizationContext(
            "interaction-1",
            target,
            endpoint,
            OpenIdentifier("http"),
            Timestamp(1_700_000_000, 0),
            "none",
        ),
        transport_context=TransportContext("interaction-1", _LIMITS),
        interaction_context=context,
        resources=resources,
        monitors=(monitor,),
        completed_event=completed,
        assembler=ModelOutputAssembler(),
        policy=CompatibilityPolicy(OpenIdentifier("strict")),
        output_id="output-1",
    )


def test_system_http_transport_success_matches_the_mock_output() -> None:
    """Verify the real HTTP stack yields the mock success output."""
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=_RESPONSE_BODY,
    )
    target = _Target()
    request: ModelRequest = _Request(target)
    parsed = ParsedTaskResponse(
        cast(ModelTaskResult, _TaskValue("vendor.result")),
        OutputStatus(OpenIdentifier("completed")),
    )
    mock_recorder = ComponentCallRecorder()
    http_recorder = ComponentCallRecorder()
    mock_response = TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("success")),
            Headers((HeaderField("Content-Type", "application/json"),)),
            status_code=200,
            media_type=MediaType("application", "json"),
        ),
        Bytes(_RESPONSE_BODY),
    )

    with MockHttpServer((script,)) as server:
        endpoint = server.uri
        plan = _plan(endpoint)
        system_transport = DefaultSystemHttpTransport(proxy_environment={})
        mock_output, http_output = asyncio.run(
            _compare(
                request=request,
                target=target,
                endpoint=endpoint,
                plan=plan,
                parsed=parsed,
                mock_recorder=mock_recorder,
                http_recorder=http_recorder,
                mock_response=mock_response,
                system_transport=system_transport,
            )
        )
        recorded = server.requests

    assert mock_recorder.calls == _SUCCESS_CALLS
    assert http_recorder.calls == _SUCCESS_CALLS
    assert "error-decode" not in http_recorder.calls
    assert "parse-error" not in http_recorder.calls
    assert len(recorded) == 1
    assert recorded[0].method == "POST"
    assert recorded[0].target == "/"
    assert recorded[0].body == b"{}"
    assert "application/json" in recorded[0].headers.get_all("Accept")
    assert "mconet-sdk" in recorded[0].headers.get_all("User-Agent")
    assert http_output.id == mock_output.id == "output-1"
    assert http_output.target is mock_output.target is target
    assert http_output.status is mock_output.status is parsed.status
    assert http_output.result is mock_output.result is parsed.result
    assert http_output.resolved_model is mock_output.resolved_model
    assert http_output.stop_reason is mock_output.stop_reason
    assert http_output.usage is mock_output.usage
    assert http_output.diagnostics == mock_output.diagnostics == ()
    assert http_output.protocol_state == mock_output.protocol_state == ()
    assert http_output.extensions == mock_output.extensions


async def _compare(
    *,
    request: ModelRequest,
    target: ModelTarget,
    endpoint: UriValue,
    plan: ProtocolExecutionPlan,
    parsed: ParsedTaskResponse,
    mock_recorder: ComponentCallRecorder,
    http_recorder: ComponentCallRecorder,
    mock_response: TransportResponse,
    system_transport: DefaultSystemHttpTransport,
) -> tuple[ModelOutput, ModelOutput]:
    """Run the mock path and the system HTTP path, then close the transport."""
    mock_transport = _RecordingTransport(
        mock_recorder,
        MockTransport(
            ComponentDescriptor("mock-transport", "1.0.0", "application"),
            mock_response,
        ),
    )
    http_transport = _RecordingTransport(
        http_recorder,
        cast(Transport, system_transport),
    )
    try:
        mock_output = await _run(
            request=request,
            target=target,
            endpoint=endpoint,
            components=_components(mock_recorder, mock_transport, plan, parsed),
            plan=plan,
        )
        http_output = await _run(
            request=request,
            target=target,
            endpoint=endpoint,
            components=_components(
                http_recorder,
                cast(Transport, http_transport),
                plan,
                parsed,
            ),
            plan=plan,
        )
    finally:
        # The SDK-owned transport must not keep the loopback connection after
        # the success case has read the response.
        await system_transport.close()
    return mock_output, http_output
