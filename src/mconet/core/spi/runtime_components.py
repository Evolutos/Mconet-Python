"""Immutable direct-injection inputs for initial runtime component roles."""

from __future__ import annotations

from dataclasses import dataclass

from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver
from mconet.core.spi.payload_decoder import PayloadDecoder
from mconet.core.spi.payload_encoder import PayloadEncoder
from mconet.core.spi.service_access_resolver import ServiceAccessResolver
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter
from mconet.core.spi.transport import Transport


@dataclass(frozen=True, slots=True)
class RuntimeComponents:
    """Store explicitly injected initial runtime behavior components.

    Client and single-interaction configuration use this same immutable carrier.
    Every single-value field directly holds one concrete behavior implementation;
    ``authorization_handlers`` directly holds an ordered immutable candidate set.
    No field contains a component ID, registry key, binding reference, factory
    name, generic role map, or deferred lookup instruction.

    ``None`` means that the configuration layer does not override that single
    role. An empty authorization handler tuple contributes no candidates. Later
    fixed Runtime algorithms merge configuration layers, select components, and
    validate behavior protocols, type contracts, capabilities, and lifecycles.

    Only executable initial-release roles are present. Monitoring uses its own
    options, while streaming, artifacts, operations, and injectable capability
    providers remain absent until their complete behavior contracts exist.
    """

    model_integration_resolver: ModelIntegrationResolver | None = None
    """Optional direct model integration resolver replacement."""

    task_protocol_adapter: TaskProtocolAdapter | None = None
    """Optional direct task protocol adapter with highest component precedence."""

    service_access_resolver: ServiceAccessResolver | None = None
    """Optional direct service access configuration resolver."""

    payload_encoder: PayloadEncoder | None = None
    """Optional direct protocol-payload encoder."""

    success_payload_decoder: PayloadDecoder | None = None
    """Optional direct decoder for successful transport outcomes."""

    error_payload_decoder: PayloadDecoder | None = None
    """Optional direct decoder for service-error transport outcomes."""

    transport: Transport | None = None
    """Optional direct unary transport implementation."""

    authorization_handler_resolver: AuthorizationHandlerResolver | None = None
    """Optional direct authorization handler resolver replacement."""

    authorization_handlers: tuple[AuthorizationHandler, ...] = ()
    """Ordered immutable authorization handler candidates contributed by the layer."""
