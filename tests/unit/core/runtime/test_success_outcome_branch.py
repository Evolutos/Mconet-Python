"""Tests for the successful transport-outcome decoder branch."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Bytes,
    ModelInteractionError,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._success_outcome_branch import (
    resolve_success_outcome_decoder,
)
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
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


class _Decoder:
    """Decoder that records whether this branch invoked it."""

    def __init__(self, name: str) -> None:
        """Store diagnostic metadata and an empty call count."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application")
        self.decode_calls = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record a decode that this branch must not perform."""
        del raw_data
        self.decode_calls += 1
        return ErasedRuntimeValue(OpenIdentifier("json.value"), None)


def _components(
    success: _Decoder,
    error: _Decoder,
) -> InteractionExecutionComponents:
    """Store the two preselected decoders and leave the other roles unused."""
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=cast(ResolvedInteractionResourceLimits, unused),
        task_protocol_adapter=cast(TaskProtocolAdapter, unused),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, unused),
        success_payload_decoder=cast(PayloadDecoder, success),
        error_payload_decoder=cast(PayloadDecoder, error),
        transport=cast(Transport, unused),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, unused),
        authorization_handlers=(),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def test_success_outcome_uses_only_the_fixed_success_decoder() -> None:
    """Verify a success outcome does not decode or switch to the error decoder."""
    success = _Decoder("success")
    error = _Decoder("error")
    selected = resolve_success_outcome_decoder(
        _components(success, error),
        TransportOutcome(OpenIdentifier("success")),
    )
    rejected = _capture(
        lambda: resolve_success_outcome_decoder(
            _components(success, error),
            TransportOutcome(OpenIdentifier("service_error")),
        )
    )

    assert selected is success
    assert selected is not error
    assert success.decode_calls == 0
    assert error.decode_calls == 0
    assert isinstance(rejected, ModelInteractionError)
    assert rejected.code == "unexpected_transport_outcome"
