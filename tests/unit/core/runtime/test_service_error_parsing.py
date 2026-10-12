"""Tests that a service error becomes one ModelInteractionError."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    ErrorCategory,
    Headers,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._service_error_parsing import parse_service_error
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
    TransportOutcome,
    TransportResponseMetadata,
)


class _Adapter:
    """Adapter that records which parse method ran."""

    def __init__(self, result: object, *, raise_result: bool = False) -> None:
        """Store the value or error produced by ``parse_error``."""
        self.descriptor = ComponentDescriptor("adapter", "1.0.0", "application")
        self.result = result
        self.raise_result = raise_result
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
        """Record a success parse that this stage must not perform."""
        del response
        self.calls.append("parse_response")
        return self.result

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Record the error parse and return or raise the prepared result."""
        del error, metadata
        self.calls.append("parse_error")
        if self.raise_result and isinstance(self.result, BaseException):
            raise self.result
        return cast(ModelInteractionError | None, self.result)


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


def _metadata() -> TransportResponseMetadata:
    """Return transport facts without a response body."""
    return TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("service_error")),
        Headers(),
        status_code=500,
        request_id="req-500",
    )


def _payload() -> ErasedRuntimeValue:
    """Return a decoded error payload whose text must not enter the message."""
    return ErasedRuntimeValue(
        OpenIdentifier("json.value"),
        {"error": "mconet-test-bearer-token-not-secret"},
    )


def test_recognized_service_error_is_preserved() -> None:
    """Verify a mapped service error is returned without parse_response."""
    expected = ModelInteractionError(
        ErrorCategory(OpenIdentifier("model_service")),
        InteractionPhase(OpenIdentifier("response_parsing")),
        "service_error",
        "The service rejected the request.",
    )
    adapter = _Adapter(expected)
    result = parse_service_error(_components(adapter), _payload(), _metadata())

    assert result is expected
    assert adapter.calls == ["parse_error"]


def test_unrecognized_service_error_uses_transport_facts_only() -> None:
    """Verify None becomes a fallback that omits the payload text."""
    adapter = _Adapter(None)
    result = parse_service_error(_components(adapter), _payload(), _metadata())

    assert result.code == "unrecognized_service_error"
    assert result.category == ErrorCategory(OpenIdentifier("model_service"))
    assert result.phase == InteractionPhase(OpenIdentifier("response_parsing"))
    assert result.status_code == 500
    assert result.request_id == "req-500"
    assert "mconet-test-bearer-token-not-secret" not in result.message
    assert adapter.calls == ["parse_error"]


def test_adapter_interaction_error_is_preserved() -> None:
    """Verify a parser ModelInteractionError is not wrapped again."""
    expected = ModelInteractionError(
        ErrorCategory(OpenIdentifier("protocol")),
        InteractionPhase(OpenIdentifier("response_parsing")),
        "invalid_service_error",
        "The service error is invalid.",
    )
    adapter = _Adapter(expected, raise_result=True)
    try:
        parse_service_error(_components(adapter), _payload(), _metadata())
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected parsing to fail.")

    assert raised is expected
    assert adapter.calls == ["parse_error"]


def test_unknown_parse_failure_is_normalized() -> None:
    """Verify an unknown parser failure omits the payload text."""
    adapter = _Adapter(
        RuntimeError("mconet-test-bearer-token-not-secret"),
        raise_result=True,
    )
    try:
        parse_service_error(_components(adapter), _payload(), _metadata())
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected parsing to fail.")

    assert raised.code == "service_error_parsing_failed"
    assert raised.category == ErrorCategory(OpenIdentifier("protocol"))
    assert raised.phase == InteractionPhase(OpenIdentifier("response_parsing"))
    assert "mconet-test-bearer-token-not-secret" not in raised.message
    assert adapter.calls == ["parse_error"]
    assert isinstance(raised.cause, RuntimeError)
