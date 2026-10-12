"""Tests for scheduled authorization handler resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Authorization,
    ModelInteractionError,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._authorization_handler_resolution import (
    resolve_interaction_authorization_handler,
)
from mconet.core.runtime.default_authorization_handler_resolver import (
    DefaultAuthorizationHandlerResolver,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    BodySigningMode,
    BodySigningRequirement,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentSelectionResolution,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    MutableTransportRequest,
    PayloadDecoder,
    PayloadEncoder,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


class _Authorization:
    """Opaque decision with no credential payload."""

    def __init__(self) -> None:
        """Store the handler discriminator."""
        self.kind = OpenIdentifier("authorization.none")


class _Handler:
    """Candidate that records support and apply calls."""

    def __init__(self, supported: frozenset[BodySigningMode]) -> None:
        """Store the modes this candidate reports."""
        self.descriptor = ComponentDescriptor("handler", "1.0.0", "application")
        self._supported = supported
        self.apply_calls = 0

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return the configured modes without reading a credential."""
        del authorization, body_signing_requirement
        return self._supported

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Record an application that resolution must not perform."""
        del authorization, context, request
        self.apply_calls += 1


class _Transport:
    """Transport that resolution must not send through."""

    def __init__(self) -> None:
        """Store diagnostic metadata and an empty call list."""
        self.descriptor = ComponentDescriptor("transport", "1.0.0", "application")
        self.calls: list[str] = []

    async def send(self, *values: object) -> object:
        """Record a send that resolution must not perform."""
        del values
        self.calls.append("send")
        return object()


def _components(
    handlers: tuple[_Handler, ...],
    transport: _Transport,
) -> InteractionExecutionComponents:
    """Store the default resolver, candidates, and an unused transport."""
    unused = object()
    return InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=cast(ResolvedInteractionResourceLimits, unused),
        task_protocol_adapter=cast(TaskProtocolAdapter, unused),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, unused),
        success_payload_decoder=cast(PayloadDecoder, unused),
        error_payload_decoder=cast(PayloadDecoder, unused),
        transport=cast(Transport, transport),
        authorization_handler_resolver=cast(
            AuthorizationHandlerResolver,
            DefaultAuthorizationHandlerResolver(),
        ),
        authorization_handlers=cast(tuple[AuthorizationHandler, ...], handlers),
        capability_resolution=cast(CapabilityResolution, unused),
    )


def test_none_and_many_fail_without_apply_or_send() -> None:
    """Verify the two cardinality failures stay distinct and do not continue."""
    idle = _Handler(frozenset())
    first = _Handler(frozenset(("none",)))
    second = _Handler(frozenset(("none",)))
    idle_transport = _Transport()
    many_transport = _Transport()
    missing = _capture(
        lambda: resolve_interaction_authorization_handler(
            _components((idle,), idle_transport),
            _Authorization(),
            BodySigningRequirement(),
        )
    )
    ambiguous = _capture(
        lambda: resolve_interaction_authorization_handler(
            _components((first, second), many_transport),
            _Authorization(),
            BodySigningRequirement(),
        )
    )

    assert isinstance(missing, ModelInteractionError)
    assert missing.code == "unsupported_authorization"
    assert isinstance(ambiguous, ModelInteractionError)
    assert ambiguous.code == "ambiguous_authorization_handler"
    assert idle.apply_calls == 0
    assert first.apply_calls == 0
    assert second.apply_calls == 0
    assert idle_transport.calls == []
    assert many_transport.calls == []
