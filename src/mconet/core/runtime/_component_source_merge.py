"""Deterministic internal merging of runtime component source layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi import (
    ModelIntegrationPlan,
    RuntimeComponent,
    RuntimeComponents,
)

ComponentSourceLayers = tuple[
    tuple[RuntimeComponent, ...],
    tuple[RuntimeComponent, ...],
    tuple[RuntimeComponent, ...],
    tuple[RuntimeComponent, ...],
]


@dataclass(frozen=True, slots=True)
class _MergedComponentSources:
    """Store role candidates in fixed source-precedence order.

    Every ``ComponentSourceLayers`` value contains exactly four immutable tuples:
    interaction injection, Client injection, integration-plan candidates, and
    SDK defaults. Empty tuples preserve an absent layer without collapsing its
    priority position. Later selection owns compatibility filtering, uniqueness,
    missing-component errors, and conversion to ``SelectedComponent`` values.

    Authorization handlers are input-dispatched candidates rather than one
    single-value role, so their field is the stable concatenation of all four
    layers. Their dedicated resolver must evaluate the complete tuple and may
    not treat this stored order as a tie-breaker.
    """

    task_protocol_adapter: ComponentSourceLayers
    """Adapter candidates from direct injection, the plan, and SDK defaults."""

    service_access_resolver: ComponentSourceLayers
    """Three direct resolver sources with an explicit empty integration layer."""

    payload_encoder: ComponentSourceLayers
    """Request encoder candidates retained within their original source layers."""

    success_payload_decoder: ComponentSourceLayers
    """Success decoder candidates retained for later plan-based selection."""

    error_payload_decoder: ComponentSourceLayers
    """Error decoder candidates retained independently from success candidates."""

    transport: ComponentSourceLayers
    """Unary transport candidates retained within their original source layers."""

    authorization_handler_resolver: ComponentSourceLayers
    """Three direct resolver sources with an explicit empty integration layer."""

    authorization_handlers: tuple[RuntimeComponent, ...]
    """All handler candidates concatenated in deterministic source order."""


def merge_component_sources(
    interaction_components: RuntimeComponents | None,
    client_components: RuntimeComponents | None,
    integration_plan: ModelIntegrationPlan,
    sdk_defaults: RuntimeComponents,
) -> _MergedComponentSources:
    """Merge four component sources without selecting or validating a role."""
    # Normalize absent optional configuration layers once. Empty carriers retain
    # the same field vocabulary without constructing placeholder components.
    interaction = _components_or_empty(
        interaction_components,
        "interaction_components",
    )
    client = _components_or_empty(client_components, "client_components")

    # The resolved integration plan and SDK defaults are mandatory source-layer
    # inputs. Nominal checks keep malformed dynamic calls from failing later with
    # partial attribute access while leaving role/SPI validation to later gates.
    plan_value = cast(object, integration_plan)
    defaults_value = cast(object, sdk_defaults)
    if not isinstance(plan_value, ModelIntegrationPlan):
        raise TypeError("integration_plan must be a ModelIntegrationPlan.")
    if not isinstance(defaults_value, RuntimeComponents):
        raise TypeError("sdk_defaults must be RuntimeComponents.")

    # Single-value roles preserve all four layers. Later selection examines only
    # the highest applicable layer, so an incompatible explicit override cannot
    # silently fall back while integration candidates still retain same-layer
    # multiplicity for deterministic ambiguity handling.
    task_protocol_adapter = _layers(
        _single(interaction.task_protocol_adapter),
        _single(client.task_protocol_adapter),
        (integration_plan.task_protocol_adapter,),
        _single(sdk_defaults.task_protocol_adapter),
    )
    service_access_resolver = _layers(
        _single(interaction.service_access_resolver),
        _single(client.service_access_resolver),
        (),
        _single(sdk_defaults.service_access_resolver),
    )
    payload_encoder = _layers(
        _single(interaction.payload_encoder),
        _single(client.payload_encoder),
        integration_plan.payload_encoders,
        _single(sdk_defaults.payload_encoder),
    )
    success_payload_decoder = _layers(
        _single(interaction.success_payload_decoder),
        _single(client.success_payload_decoder),
        integration_plan.payload_decoders,
        _single(sdk_defaults.success_payload_decoder),
    )
    error_payload_decoder = _layers(
        _single(interaction.error_payload_decoder),
        _single(client.error_payload_decoder),
        integration_plan.payload_decoders,
        _single(sdk_defaults.error_payload_decoder),
    )
    transport = _layers(
        _single(interaction.transport),
        _single(client.transport),
        integration_plan.transports,
        _single(sdk_defaults.transport),
    )
    authorization_handler_resolver = _layers(
        _single(interaction.authorization_handler_resolver),
        _single(client.authorization_handler_resolver),
        (),
        _single(sdk_defaults.authorization_handler_resolver),
    )

    # List roles append rather than shadow lower layers. Preserve every exact
    # instance and declaration order; deduplication or name-based sorting could
    # hide a real ambiguity from the dedicated authorization resolver.
    authorization_handlers: tuple[RuntimeComponent, ...] = (
        *interaction.authorization_handlers,
        *client.authorization_handlers,
        *integration_plan.authorization_handlers,
        *sdk_defaults.authorization_handlers,
    )

    # The frozen result contains source facts only. It neither creates selected
    # component snapshots nor evaluates plans, descriptors, capabilities, or I/O.
    return _MergedComponentSources(
        task_protocol_adapter=task_protocol_adapter,
        service_access_resolver=service_access_resolver,
        payload_encoder=payload_encoder,
        success_payload_decoder=success_payload_decoder,
        error_payload_decoder=error_payload_decoder,
        transport=transport,
        authorization_handler_resolver=authorization_handler_resolver,
        authorization_handlers=authorization_handlers,
    )


def _components_or_empty(
    value: RuntimeComponents | None,
    parameter_name: str,
) -> RuntimeComponents:
    """Return one supplied configuration layer or a typed empty carrier."""
    # None means that the configuration layer contributes no overrides. Reject
    # unrelated dynamic objects rather than interpreting arbitrary attributes as
    # a hidden component map or service locator.
    if value is None:
        return RuntimeComponents()
    candidate = cast(object, value)
    if not isinstance(candidate, RuntimeComponents):
        raise TypeError(f"{parameter_name} must be RuntimeComponents or None.")
    return value


def _single(component: RuntimeComponent | None) -> tuple[RuntimeComponent, ...]:
    """Represent an optional direct component as zero or one candidate."""
    # The singleton conversion retains concrete identity and never checks role
    # behavior, descriptor compatibility, or selection conditions prematurely.
    if component is None:
        return ()
    return (component,)


def _layers(
    interaction: tuple[RuntimeComponent, ...],
    client: tuple[RuntimeComponent, ...],
    integration: tuple[RuntimeComponent, ...],
    sdk_default: tuple[RuntimeComponent, ...],
) -> ComponentSourceLayers:
    """Build one role's fixed four-position immutable source sequence."""
    # Keeping empty tuples in place makes source precedence structural. Later
    # selection never infers a source from descriptor metadata or tuple length.
    return interaction, client, integration, sdk_default
