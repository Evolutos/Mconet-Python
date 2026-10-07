"""Immutable component snapshot for one initial runtime interaction."""

from __future__ import annotations

from dataclasses import dataclass

from mconet.core.domain import ResolvedInteractionResourceLimits
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.capability_resolution import CapabilityResolution
from mconet.core.spi.component_selection_resolution import (
    ComponentSelectionResolution,
)
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.payload_decoder import PayloadDecoder
from mconet.core.spi.payload_encoder import PayloadEncoder
from mconet.core.spi.service_access_resolver import ServiceAccessResolver
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter
from mconet.core.spi.transport import Transport


@dataclass(frozen=True, slots=True)
class InteractionExecutionComponents:
    """Fix every validated component used by one initial interaction.

    Runtime creates this value only after integration planning, component
    selection, type-contract validation, capability resolution, and resource
    limit resolution have succeeded. Every single-value role is therefore
    required rather than optional, while authorization handlers remain an
    immutable candidate tuple for their input-specific resolver.

    The snapshot stores exact component instances and completed resolution
    values. It performs no registry lookup, component selection, validation,
    default insertion, factory invocation, or request execution. Later Runtime
    stages can consequently use one stable object graph even if Client or plugin
    configuration changes while the interaction is in progress.

    Only the executable initial unary path is represented. Streaming, artifacts,
    operations, injectable capability providers, and monitoring acquire their
    own fields or option containers only when their complete contracts exist.
    """

    integration_plan: ModelIntegrationPlan
    """Resolved integration provenance and binding-owned component snapshot."""

    component_selection: ComponentSelectionResolution
    """Completed unique selection result for single-value component roles."""

    resource_limits: ResolvedInteractionResourceLimits
    """Finite byte limits resolved for this exact interaction."""

    task_protocol_adapter: TaskProtocolAdapter
    """Unique adapter used for planning, request mapping, and response parsing."""

    service_access_resolver: ServiceAccessResolver
    """Unique side-effect-free service access resolver."""

    payload_encoder: PayloadEncoder
    """Unique encoder fixed before authorization and transport execution."""

    success_payload_decoder: PayloadDecoder
    """Preselected decoder for successful transport outcomes."""

    error_payload_decoder: PayloadDecoder
    """Preselected decoder for service-error transport outcomes."""

    transport: Transport
    """Unique unary transport used after request authorization and freezing."""

    authorization_handler_resolver: AuthorizationHandlerResolver
    """Unique resolver for the immutable authorization candidate set."""

    authorization_handlers: tuple[AuthorizationHandler, ...]
    """Ordered immutable authorization handlers available to this interaction."""

    capability_resolution: CapabilityResolution
    """Completed required and optional capability resolution facts."""
