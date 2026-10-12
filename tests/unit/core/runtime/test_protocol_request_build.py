"""Tests that request building returns only a protocol request plan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import (
    ErrorCategory,
    Extensions,
    Headers,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    ModelRequest,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    UriValue,
)
from mconet.core.runtime._protocol_request_build import build_protocol_request
from mconet.core.spi import (
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
    PayloadDecoder,
    PayloadEncoder,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
    TransportRequestPlan,
    TransportSelection,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization with no credential payload."""

    kind: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request. Building does not read its fields."""

    target: object
    task: object
    service_access: None
    metadata: Extensions
    extensions: Extensions


class _Adapter:
    """Adapter that records every behavior call."""

    def __init__(self, result: object) -> None:
        """Store the value ``build_request`` will return."""
        self.result = result
        self.calls: list[str] = []
        self.descriptor = ComponentDescriptor("adapter", "1.0.0", "application")

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
        """Record the one mapping call and return the prepared result."""
        del values
        self.calls.append("build_request")
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def parse_response(self, *values: object) -> object:
        """Record a response-parsing call."""
        del values
        self.calls.append("parse_response")
        return self.result

    def parse_error(self, *values: object) -> object:
        """Record an error-parsing call."""
        del values
        self.calls.append("parse_error")
        return None


class _Encoder:
    """Encoder that building must not call."""

    def __init__(self) -> None:
        """Store diagnostic metadata and an empty call list."""
        self.calls: list[str] = []
        self.descriptor = ComponentDescriptor("encoder", "1.0.0", "application")

    def encode(self, *values: object) -> object:
        """Record an encoding call."""
        del values
        self.calls.append("encode")
        return object()


def _execution_plan() -> ProtocolExecutionPlan:
    """Return one plan the adapter pairs with its payload."""
    media_type = MediaType("application", "json")
    return ProtocolExecutionPlan(
        transport_plan=TransportRequestPlan(
            endpoint=UriValue("https://models.example.test", True),
            path="/v1/chat/completions",
            method="POST",
            headers=Headers(),
            query=QueryParameters(),
            authorization=_Authorization(OpenIdentifier("authorization.none")),
            body_signing_requirement=BodySigningRequirement(),
        ),
        payload_encoder=EncoderSelection(media_type),
        success_decoder=DecoderSelection(media_type),
        error_decoder=DecoderSelection(media_type),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def _request_plan(execution_plan: ProtocolExecutionPlan) -> ProtocolRequestPlan:
    """Return the protocol plan the adapter is expected to produce."""
    payload = ErasedRuntimeValue(OpenIdentifier("json.value"), {"model": "m"})
    return ProtocolRequestPlan(payload, execution_plan)


def _components(adapter: _Adapter, encoder: _Encoder) -> InteractionExecutionComponents:
    """Store the adapter and encoder without constructing the other roles."""
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=cast(ResolvedInteractionResourceLimits, unused),
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, encoder),
        success_payload_decoder=cast(PayloadDecoder, unused),
        error_payload_decoder=cast(PayloadDecoder, unused),
        transport=cast(Transport, unused),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, unused),
        authorization_handlers=(),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def _request() -> _Request:
    """Return a request whose fields building does not inspect."""
    return _Request(object(), object(), None, {}, {})


def test_build_request_returns_the_protocol_plan_once() -> None:
    """Verify mapping does not encode and is not repeated."""
    execution_plan = _execution_plan()
    request_plan = _request_plan(execution_plan)
    adapter = _Adapter(request_plan)
    encoder = _Encoder()

    built = build_protocol_request(
        cast(ModelRequest, _request()),
        _components(adapter, encoder),
        execution_plan,
    )

    assert built is request_plan
    assert adapter.calls == ["build_request"]
    assert encoder.calls == []


def test_mapping_failure_is_not_retried() -> None:
    """Verify one adapter failure stays a single call."""
    failure = ModelInteractionError(
        ErrorCategory(OpenIdentifier("invalid_request")),
        InteractionPhase(OpenIdentifier("protocol_adaptation")),
        "invalid_request",
        "The request could not be mapped.",
    )
    adapter = _Adapter(failure)
    error = _capture(
        lambda: build_protocol_request(
            cast(ModelRequest, _request()),
            _components(adapter, _Encoder()),
            _execution_plan(),
        )
    )

    assert error is failure
    assert adapter.calls == ["build_request"]
