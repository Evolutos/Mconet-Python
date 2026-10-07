"""Construction of validated component snapshots for unary interactions."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
    validate_resource_limits,
)
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentRole,
    ComponentSelectionResolution,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    PayloadDecoder,
    PayloadEncoder,
    RuntimeComponent,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
)

_TASK_PROTOCOL_ADAPTER_ROLE = ComponentRole(OpenIdentifier("task.protocol-adapter"))
_PAYLOAD_ENCODER_ROLE = ComponentRole(OpenIdentifier("codec.request.encoder"))
_SUCCESS_PAYLOAD_DECODER_ROLE = ComponentRole(
    OpenIdentifier("codec.response.success-decoder")
)
_ERROR_PAYLOAD_DECODER_ROLE = ComponentRole(
    OpenIdentifier("codec.response.error-decoder")
)
_TRANSPORT_ROLE = ComponentRole(OpenIdentifier("transport.unary"))
_REQUIRED_ROLES = frozenset(
    (
        _TASK_PROTOCOL_ADAPTER_ROLE,
        _PAYLOAD_ENCODER_ROLE,
        _SUCCESS_PAYLOAD_DECODER_ROLE,
        _ERROR_PAYLOAD_DECODER_ROLE,
        _TRANSPORT_ROLE,
    )
)


def create_interaction_execution_components(
    *,
    integration_plan: ModelIntegrationPlan,
    component_selection: ComponentSelectionResolution,
    resource_limits: ResolvedInteractionResourceLimits,
    service_access_resolver: ServiceAccessResolver,
    authorization_handler_resolver: AuthorizationHandlerResolver,
    authorization_handlers: tuple[AuthorizationHandler, ...],
    capability_resolution: CapabilityResolution,
) -> InteractionExecutionComponents:
    """Create one immutable unary execution snapshot from completed results.

    The five executable single-value components are derived exclusively from
    ``component_selection`` under Core-owned roles. Callers cannot supply a
    second adapter, codec, or transport instance that disagrees with selection.
    Every selected executable role must expose its exact behavior protocol and
    a non-null type contract, enforcing the minimum post-validation invariant.

    Integration planning, resource-limit resolution, authorization candidate
    collection, and capability resolution arrive as completed immutable values.
    This factory validates their nominal boundaries and preserves every exact
    object and tuple; it performs no component lookup, default insertion,
    capability matching, port compatibility calculation, behavior invocation,
    factory creation, network access, or request mutation.

    Returns:
        A frozen interaction-owned component graph for the unary execution path.

    Raises:
        TypeError: If a completed value, behavior protocol, descriptor, or
            immutable candidate collection has the wrong runtime type.
        ValueError: If resource limits are invalid, the component selection has
            missing or unsupported roles, or a selected role has no type contract.
    """
    plan_value = cast(object, integration_plan)
    selection_value = cast(object, component_selection)
    limits_value = cast(object, resource_limits)
    capability_value = cast(object, capability_resolution)

    # Require nominal completed aggregates before reading any nested values.
    # Structural look-alikes cannot claim that planning or resolution occurred.
    if not isinstance(plan_value, ModelIntegrationPlan):
        raise TypeError("integration_plan must be a ModelIntegrationPlan.")
    if not isinstance(selection_value, ComponentSelectionResolution):
        raise TypeError("component_selection must be a ComponentSelectionResolution.")
    if not isinstance(limits_value, ResolvedInteractionResourceLimits):
        raise TypeError("resource_limits must be a ResolvedInteractionResourceLimits.")
    if not isinstance(capability_value, CapabilityResolution):
        raise TypeError("capability_resolution must be a CapabilityResolution.")

    # Recheck semantic limit completion at the final retention boundary. The
    # validator returns the same object, so no interaction configuration is copied.
    validate_resource_limits(resource_limits)

    # Resolver roles and handler candidates are input-dispatched components, not
    # ComponentRole entries. Validate their exact behavior and immutable shape
    # independently before constructing the final snapshot.
    _validate_behavior_component(
        service_access_resolver,
        ServiceAccessResolver,
        "service_access_resolver",
    )
    _validate_behavior_component(
        authorization_handler_resolver,
        AuthorizationHandlerResolver,
        "authorization_handler_resolver",
    )
    handlers_value = cast(object, authorization_handlers)
    if not isinstance(handlers_value, tuple):
        raise TypeError("authorization_handlers must be a tuple.")
    for handler in cast(tuple[object, ...], handlers_value):
        _validate_behavior_component(
            handler,
            AuthorizationHandler,
            "authorization_handlers",
        )

    # Role uniqueness was established by ComponentSelectionResolution. Rebuild a
    # private lookup without copying component objects or exposing an open role map.
    selected_by_role = {
        selected.role: selected.component for selected in component_selection.components
    }
    if frozenset(selected_by_role) != _REQUIRED_ROLES:
        # A missing role means selection is incomplete; an extra role would be
        # silently lost because the current unary snapshot has no matching field.
        raise ValueError(
            "component_selection must contain exactly the unary execution roles."
        )

    task_protocol_adapter = selected_by_role[_TASK_PROTOCOL_ADAPTER_ROLE]
    payload_encoder = selected_by_role[_PAYLOAD_ENCODER_ROLE]
    success_payload_decoder = selected_by_role[_SUCCESS_PAYLOAD_DECODER_ROLE]
    error_payload_decoder = selected_by_role[_ERROR_PAYLOAD_DECODER_ROLE]
    transport = selected_by_role[_TRANSPORT_ROLE]

    # Integration resolution and component selection must converge on the same
    # adapter object. Equality is insufficient because stateful application
    # implementations could compare equal while representing different owners.
    if task_protocol_adapter is not integration_plan.task_protocol_adapter:
        raise ValueError(
            "selected task_protocol_adapter must match the integration plan."
        )

    # Behavior checks ensure metadata-only components cannot enter executable
    # fields. Type-contract presence prevents an obviously incomplete selection;
    # port compatibility remains owned by the preceding dedicated validator and
    # is intentionally not recalculated or inferred at this construction step.
    _validate_selected_component(
        task_protocol_adapter,
        TaskProtocolAdapter,
        "task_protocol_adapter",
    )
    _validate_selected_component(
        payload_encoder,
        PayloadEncoder,
        "payload_encoder",
    )
    _validate_selected_component(
        success_payload_decoder,
        PayloadDecoder,
        "success_payload_decoder",
    )
    _validate_selected_component(
        error_payload_decoder,
        PayloadDecoder,
        "error_payload_decoder",
    )
    _validate_selected_component(transport, Transport, "transport")

    # Every retained object is the exact completed input or selected instance.
    # InteractionExecutionComponents is a carrier and performs no later lookup.
    return InteractionExecutionComponents(
        integration_plan=integration_plan,
        component_selection=component_selection,
        resource_limits=resource_limits,
        task_protocol_adapter=cast(TaskProtocolAdapter, task_protocol_adapter),
        service_access_resolver=service_access_resolver,
        payload_encoder=cast(PayloadEncoder, payload_encoder),
        success_payload_decoder=cast(PayloadDecoder, success_payload_decoder),
        error_payload_decoder=cast(PayloadDecoder, error_payload_decoder),
        transport=cast(Transport, transport),
        authorization_handler_resolver=authorization_handler_resolver,
        authorization_handlers=authorization_handlers,
        capability_resolution=capability_resolution,
    )


def _validate_selected_component(
    value: object,
    behavior: type[object],
    field_name: str,
) -> None:
    """Require selected executable behavior with declared type-contract facts."""
    _validate_behavior_component(value, behavior, field_name)
    descriptor = cast(RuntimeComponent, value).descriptor

    # All current selected roles exchange data across an execution-chain port.
    # None is valid only for components with no ports and therefore cannot satisfy
    # the minimum completed-input boundary for these data-bearing unary roles.
    if descriptor.type_contract is None:
        raise ValueError(f"selected {field_name} must declare a type contract.")


def _validate_behavior_component(
    value: object,
    behavior: type[object],
    field_name: str,
) -> None:
    """Require one structural behavior component with nominal metadata."""
    # Runtime-checkable protocols make application and plugin implementations
    # eligible without inheritance while still excluding a descriptor-only value.
    if not isinstance(value, behavior):
        raise TypeError(f"{field_name} must implement the declared behavior protocol.")

    # Protocol checks prove only member presence. A nominal descriptor prevents
    # malformed dynamic metadata from bypassing the completed selection boundary.
    descriptor = cast(object, cast(RuntimeComponent, value).descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(f"{field_name} descriptor must be a ComponentDescriptor.")
