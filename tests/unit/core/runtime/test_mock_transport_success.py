"""Mock-transport success chain order and output."""

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
    Headers,
    MediaType,
    ModelDescriptor,
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
    MockTransport,
    StubInteractionMonitor,
)


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
    """Adapter that records build and parse and returns fixed values."""

    def __init__(
        self,
        recorder: ComponentCallRecorder,
        parsed: ParsedTaskResponse,
        plan: ProtocolExecutionPlan,
    ) -> None:
        """Store the recorder and the values later stages compare."""
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
        """Record the success parse and return the prepared response."""
        del response
        self._recorder.record("parse")
        return self._parsed

    def parse_error(self, *values: object) -> None:
        """Record an error parse that the success chain must not perform."""
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
    """Decoder that records the label supplied for its role."""

    def __init__(self, recorder: ComponentCallRecorder, label: str) -> None:
        """Store the recorder and the role label."""
        self.descriptor = ComponentDescriptor(label, "1.0.0", "application")
        self._recorder = recorder
        self._label = label

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record this decoder and return a JSON value."""
        del raw_data
        self._recorder.record(self._label)
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


class _Transport:
    """Mock transport that records the send before returning its response."""

    def __init__(
        self,
        recorder: ComponentCallRecorder,
        response: TransportResponse,
    ) -> None:
        """Wrap one mock transport."""
        self._inner = MockTransport(
            ComponentDescriptor("mock-transport", "1.0.0", "application"),
            response,
        )
        self.descriptor = self._inner.descriptor
        self._recorder = recorder

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record the send and delegate to the mock transport."""
        self._recorder.record("send")
        return await self._inner.send(request, context)


def test_mock_transport_success_matches_call_order_and_output() -> None:
    """Verify the success chain order and the assembled output owners."""
    recorder = ComponentCallRecorder()
    target = _Target()
    request: ModelRequest = _Request(target)
    status = OutputStatus(OpenIdentifier("completed"))
    result: ModelTaskResult = _TaskValue("vendor.result")
    parsed = ParsedTaskResponse(result, status)
    endpoint = UriValue("https://example.test/v1", True)
    authorization = _Authorization()
    execution_plan = ProtocolExecutionPlan(
        TransportRequestPlan(
            endpoint,
            "",
            "POST",
            Headers(),
            QueryParameters(),
            cast(Authorization, authorization),
            BodySigningRequirement(),
        ),
        EncoderSelection(),
        DecoderSelection(),
        DecoderSelection(),
        TransportSelection(OpenIdentifier("http")),
    )
    adapter = _Adapter(recorder, parsed, execution_plan)
    encoder = _Encoder(recorder)
    success_decoder = _Decoder(recorder, "decode")
    error_decoder = _Decoder(recorder, "error-decode")
    transport = _Transport(
        recorder,
        TransportResponse(
            TransportResponseMetadata(
                TransportOutcome(OpenIdentifier("success")),
                Headers(),
            ),
            Bytes(b"{}"),
        ),
    )
    unused = object()
    components = InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=ResolvedInteractionResourceLimits(100, 200, 300),
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, encoder),
        success_payload_decoder=cast(PayloadDecoder, success_decoder),
        error_payload_decoder=cast(PayloadDecoder, error_decoder),
        transport=cast(Transport, transport),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, _Resolver()),
        authorization_handlers=(cast(AuthorizationHandler, _Handler(recorder)),),
        capability_resolution=cast(CapabilityResolution, unused),
    )
    context = InteractionContext(
        request,
        ResolvedInteractionConfiguration(
            target,
            None,
            CompatibilityPolicy(OpenIdentifier("strict")),
            ResolvedInteractionResourceLimits(100, 200, 300),
            None,
        ),
    )
    resources = ResponseResources(Bytes(b"{}"), lambda: None)
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

    output = asyncio.run(
        run_mock_transport_success(
            request=request,
            components=components,
            execution_plan=execution_plan,
            authorization_context=AuthorizationContext(
                "interaction-1",
                target,
                endpoint,
                OpenIdentifier("http"),
                Timestamp(1_700_000_000, 0),
                "none",
            ),
            transport_context=TransportContext(
                "interaction-1",
                ResolvedInteractionResourceLimits(100, 200, 300),
            ),
            interaction_context=context,
            resources=resources,
            monitors=(monitor,),
            completed_event=completed,
            assembler=ModelOutputAssembler(),
            policy=CompatibilityPolicy(OpenIdentifier("strict")),
            output_id="output-1",
        )
    )

    assert recorder.calls == ("build", "encode", "authorize", "send", "decode", "parse")
    assert output.target is target
    assert output.status is status
    assert output.result is result
    assert output.id == "output-1"
    assert output.diagnostics == ()
    assert resources.released is True
    assert context.released is True
    assert [event.type for event in monitor.events] == [
        OpenIdentifier("authorization.will_resolve"),
        OpenIdentifier("interaction.completed"),
    ]
