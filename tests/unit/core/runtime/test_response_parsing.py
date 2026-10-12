"""Tests that a successful payload becomes a parsed task response."""

from __future__ import annotations

from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    ResolvedInteractionResourceLimits,
    TaskDocument,
    TaskGroupNode,
)
from mconet.core.runtime._response_parsing import parse_successful_task_response
from mconet.core.spi import (
    AuthorizationHandlerResolver,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentSelectionResolution,
    ErasedRuntimeValue,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    PayloadDecoder,
    PayloadEncoder,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
    TransportResponseMetadata,
)


class _Kind:
    """Container kind for one empty result document."""

    def __init__(self) -> None:
        """Store the kind identity and composition."""
        self.id = OpenIdentifier("task.result-root")
        self.composition: Literal["container"] = "container"


class _Descriptor:
    """Task descriptor for one structural result."""

    def __init__(self) -> None:
        """Store the minimum descriptor fields."""
        self.type = OpenIdentifier("conversation.generate")
        self.version = "1.0"
        self.input_schema_id = None
        self.output_schema_id = None
        self.metadata: dict[str, str] = {}
        self.extensions: dict[str, str] = {}


class _Result:
    """Structural task result returned inside a parsed response."""

    def __init__(self) -> None:
        """Store an empty result document."""
        self.descriptor = _Descriptor()
        self.document = TaskDocument(
            "1.0",
            TaskGroupNode("root", _Kind(), ()),
        )
        self.artifacts = ArtifactCatalog()
        self.metadata: dict[str, str] = {}
        self.extensions: dict[str, str] = {}


class _Adapter:
    """Adapter that records which parse method ran."""

    def __init__(self, result: object) -> None:
        """Store the value or error produced by ``parse_response``."""
        self.descriptor = ComponentDescriptor("adapter", "1.0.0", "application")
        self.result = result
        self.calls: list[str] = []

    def supports(self, *values: object) -> bool:
        """Record an applicability call."""
        del values
        self.calls.append("supports")
        return True

    def prepare_plan(self, *values: object) -> object:
        """Record a planning call."""
        del values
        self.calls.append("prepare_plan")
        return self.result

    def build_request(self, *values: object) -> object:
        """Record a request-building call."""
        del values
        self.calls.append("build_request")
        return self.result

    def parse_response(self, response: ErasedRuntimeValue) -> object:
        """Record the success parse and return or raise the prepared result."""
        del response
        self.calls.append("parse_response")
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Record an error parse that this stage must not perform."""
        del error, metadata
        self.calls.append("parse_error")
        return None


def _parsed() -> ParsedTaskResponse:
    """Return one parsed response with a completed status."""
    return ParsedTaskResponse(_Result(), OutputStatus(OpenIdentifier("completed")))


def _components(adapter: _Adapter) -> InteractionExecutionComponents:
    """Store the adapter and leave the other roles unused."""
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=cast(ResolvedInteractionResourceLimits, unused),
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, unused),
        success_payload_decoder=cast(PayloadDecoder, unused),
        error_payload_decoder=cast(PayloadDecoder, unused),
        transport=cast(Transport, unused),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, unused),
        authorization_handlers=(),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def test_parse_response_returns_the_parsed_task_response() -> None:
    """Verify success parsing does not call parse_error."""
    parsed = _parsed()
    adapter = _Adapter(parsed)
    result = parse_successful_task_response(
        _components(adapter),
        ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": True}),
    )

    assert result is parsed
    assert adapter.calls == ["parse_response"]


def test_unknown_parse_failure_is_normalized() -> None:
    """Verify an unknown parser failure omits the payload text."""
    adapter = _Adapter(RuntimeError("mconet-test-bearer-token-not-secret"))
    try:
        parse_successful_task_response(
            _components(adapter),
            ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": False}),
        )
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected parsing to fail.")

    assert raised.code == "response_parsing_failed"
    assert raised.category == ErrorCategory(OpenIdentifier("protocol"))
    assert raised.phase == InteractionPhase(OpenIdentifier("response_parsing"))
    assert "mconet-test-bearer-token-not-secret" not in raised.message
    assert adapter.calls == ["parse_response"]
    assert isinstance(raised.cause, RuntimeError)


def test_adapter_interaction_error_is_preserved() -> None:
    """Verify a parser ModelInteractionError is not wrapped again."""
    expected = ModelInteractionError(
        ErrorCategory(OpenIdentifier("protocol")),
        InteractionPhase(OpenIdentifier("response_parsing")),
        "invalid_task_response",
        "The task response is invalid.",
    )
    adapter = _Adapter(expected)
    try:
        parse_successful_task_response(
            _components(adapter),
            ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": False}),
        )
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected parsing to fail.")

    assert raised is expected
    assert adapter.calls == ["parse_response"]
