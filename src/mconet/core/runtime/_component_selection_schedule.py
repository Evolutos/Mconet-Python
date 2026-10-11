"""Runtime scheduling for fixed-priority single-value component selection."""

from __future__ import annotations

from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.runtime._component_source_merge import merge_component_sources
from mconet.core.runtime._protocol_plan_scope import (
    validate_r1_protocol_execution_plan,
)
from mconet.core.runtime._single_component_selection import select_required_component
from mconet.core.spi.component_role import ComponentRole
from mconet.core.spi.component_selection_resolution import ComponentSelectionResolution
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.payload_decoder import PayloadDecoder
from mconet.core.spi.payload_encoder import PayloadEncoder
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.runtime_components import RuntimeComponents
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter
from mconet.core.spi.transport import Transport

_ADAPTER_ROLE = ComponentRole(OpenIdentifier("task.protocol-adapter"))
_ENCODER_ROLE = ComponentRole(OpenIdentifier("codec.request.encoder"))
_SUCCESS_DECODER_ROLE = ComponentRole(OpenIdentifier("codec.response.success-decoder"))
_ERROR_DECODER_ROLE = ComponentRole(OpenIdentifier("codec.response.error-decoder"))
_TRANSPORT_ROLE = ComponentRole(OpenIdentifier("transport.unary"))


def select_execution_components(
    mode: InteractionMode,
    execution_plan: ProtocolExecutionPlan,
    integration_plan: ModelIntegrationPlan,
    *,
    interaction_components: RuntimeComponents | None,
    client_components: RuntimeComponents | None,
    sdk_defaults: RuntimeComponents,
) -> ComponentSelectionResolution:
    """Select each required role from the highest present source layer.

    Source order is interaction, client, integration plan, then SDK default.
    A higher layer that is present blocks every lower layer, including when
    that layer has no match or more than one match. Missing and ambiguous
    results stay separate errors. An execution plan outside the R1 scope fails
    before any role is selected.

    Args:
        mode: Interaction mode paired with the execution plan.
        execution_plan: Plan produced by the single prepare step.
        integration_plan: Integration plan that contributes binding candidates.
        interaction_components: Optional single-interaction overrides.
        client_components: Optional client defaults.
        sdk_defaults: SDK components used when no higher layer speaks.

    Returns:
        The five selected unary roles in adapter, encoder, success decoder,
        error decoder, transport order.

    Raises:
        TypeError: If a plan or component layer has an invalid type.
        ModelInteractionError: If the plan is outside the R1 scope, a required
            role has no match (``component_not_found``), or the highest present
            layer has several matches (``ambiguous_component_selection``).
    """
    # Scope failure stops the stage. Component layers are not consulted, so a
    # streaming plan cannot be rescued by an injected unary transport.
    validate_r1_protocol_execution_plan(mode, execution_plan)
    sources = merge_component_sources(
        interaction_components,
        client_components,
        integration_plan,
        sdk_defaults,
    )
    # Each role uses the same precedence. Protocol checks keep an encoder from
    # occupying a transport role. Type-contract compatibility is a later gate.
    selected = (
        select_required_component(
            _ADAPTER_ROLE,
            sources.task_protocol_adapter,
            _is_adapter,
        ),
        select_required_component(
            _ENCODER_ROLE,
            sources.payload_encoder,
            _is_encoder,
        ),
        select_required_component(
            _SUCCESS_DECODER_ROLE,
            sources.success_payload_decoder,
            _is_decoder,
        ),
        select_required_component(
            _ERROR_DECODER_ROLE,
            sources.error_payload_decoder,
            _is_decoder,
        ),
        select_required_component(
            _TRANSPORT_ROLE,
            sources.transport,
            _is_transport,
        ),
    )
    return ComponentSelectionResolution(selected)


def _is_adapter(component: RuntimeComponent) -> bool:
    """Return whether the candidate implements the task protocol adapter."""
    return isinstance(component, TaskProtocolAdapter)


def _is_encoder(component: RuntimeComponent) -> bool:
    """Return whether the candidate implements the payload encoder."""
    return isinstance(component, PayloadEncoder)


def _is_decoder(component: RuntimeComponent) -> bool:
    """Return whether the candidate implements the payload decoder."""
    return isinstance(component, PayloadDecoder)


def _is_transport(component: RuntimeComponent) -> bool:
    """Return whether the candidate implements the unary transport."""
    return isinstance(component, Transport)
