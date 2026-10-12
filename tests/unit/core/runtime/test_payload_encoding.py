"""Tests that encoding stops before authorization."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Bytes,
    ErrorCategory,
    Headers,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    UriValue,
)
from mconet.core.runtime._payload_encoding import encode_protocol_payload
from mconet.core.spi import (
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
    PayloadDecoder,
    PayloadEncoder,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
    TransportBody,
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


class _Encoder:
    """Encoder that records its single call."""

    def __init__(self, result: object) -> None:
        """Store the body or error ``encode`` will produce."""
        self.result = result
        self.calls: list[str] = []
        self.descriptor = ComponentDescriptor("encoder", "1.0.0", "application")

    def encode(self, payload: object) -> object:
        """Record the encoding call and return or raise the prepared result."""
        del payload
        self.calls.append("encode")
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _Handler:
    """Authorization handler that encoding must not apply."""

    def __init__(self) -> None:
        """Store diagnostic metadata and an empty call list."""
        self.calls: list[str] = []
        self.descriptor = ComponentDescriptor("handler", "1.0.0", "application")

    def supports(self, *values: object) -> bool:
        """Record an applicability call."""
        del values
        self.calls.append("supports")
        return True

    async def apply(self, *values: object) -> None:
        """Record an authorization call."""
        del values
        self.calls.append("apply")


def _request_plan() -> ProtocolRequestPlan:
    """Return one protocol plan whose payload can be encoded."""
    media_type = MediaType("application", "json")
    execution_plan = ProtocolExecutionPlan(
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
    payload = ErasedRuntimeValue(OpenIdentifier("json.value"), {"model": "m"})
    return ProtocolRequestPlan(payload, execution_plan)


class _Authorization:
    """Opaque authorization with no credential payload."""

    def __init__(self, kind: OpenIdentifier) -> None:
        """Store the handler discriminator."""
        self.kind = kind


def _components(
    encoder: _Encoder,
    handler: _Handler,
) -> InteractionExecutionComponents:
    """Store the encoder and one handler without constructing other roles."""
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=cast(ResolvedInteractionResourceLimits, unused),
        task_protocol_adapter=cast(TaskProtocolAdapter, unused),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, encoder),
        success_payload_decoder=cast(PayloadDecoder, unused),
        error_payload_decoder=cast(PayloadDecoder, unused),
        transport=cast(Transport, unused),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, unused),
        authorization_handlers=(cast(AuthorizationHandler, handler),),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def test_encode_returns_the_body_without_authorization() -> None:
    """Verify a successful encoding does not apply a handler."""
    body = TransportBody(Bytes(b"{}"), MediaType("application", "json"))
    encoder = _Encoder(body)
    handler = _Handler()

    encoded = encode_protocol_payload(_components(encoder, handler), _request_plan())

    assert encoded is body
    assert encoder.calls == ["encode"]
    assert handler.calls == []


def test_encode_failure_does_not_enter_authorization() -> None:
    """Verify one encoding failure is not retried and does not apply a handler."""
    failure = ModelInteractionError(
        ErrorCategory(OpenIdentifier("invalid_request")),
        InteractionPhase(OpenIdentifier("payload_encoding")),
        "payload_encoding_failed",
        "The payload could not be encoded.",
    )
    encoder = _Encoder(failure)
    handler = _Handler()
    error = _capture(
        lambda: encode_protocol_payload(_components(encoder, handler), _request_plan())
    )

    assert error is failure
    assert encoder.calls == ["encode"]
    assert handler.calls == []
