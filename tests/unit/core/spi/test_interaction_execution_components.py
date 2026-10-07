"""Completeness and immutability tests for interaction component snapshots."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast, get_type_hints

from mconet.core.domain import ResolvedInteractionResourceLimits
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    CapabilityResolution,
    ComponentDescriptor,
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


@dataclass(frozen=True, slots=True)
class _Component:
    """Distinguishable runtime-component fixture for snapshot identity tests."""

    descriptor: ComponentDescriptor
    """Immutable component metadata required by the common runtime protocol."""


def _component(name: str) -> _Component:
    """Create one component fixture with distinct diagnostic metadata."""
    # Separate instances make accidental field swaps, copying, reconstruction,
    # and candidate reordering observable without exercising component behavior.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _complete_snapshot() -> tuple[
    InteractionExecutionComponents,
    tuple[object, ...],
]:
    """Build one fully populated initial interaction component snapshot."""
    # A valid direct plan supplies real completed aggregate values, while casts
    # adapt component-shaped fixtures to behavior roles that this carrier stores
    # but deliberately does not invoke or revalidate.
    plan_component = _component("Integration adapter")
    integration_plan = ModelIntegrationPlan(
        "direct_adapter",
        None,
        None,
        None,
        cast(RuntimeComponent, plan_component),
    )
    component_selection = ComponentSelectionResolution()
    resource_limits = ResolvedInteractionResourceLimits(4_096, 1_024, 512)
    adapter = _component("Task adapter")
    access_resolver = _component("Access resolver")
    encoder = _component("Payload encoder")
    success_decoder = _component("Success decoder")
    error_decoder = _component("Error decoder")
    transport = _component("Transport")
    authorization_resolver = _component("Authorization resolver")
    first_handler = _component("First authorization handler")
    second_handler = _component("Second authorization handler")
    capability_resolution = CapabilityResolution()

    snapshot = InteractionExecutionComponents(
        integration_plan=integration_plan,
        component_selection=component_selection,
        resource_limits=resource_limits,
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        service_access_resolver=cast(ServiceAccessResolver, access_resolver),
        payload_encoder=cast(PayloadEncoder, encoder),
        success_payload_decoder=cast(PayloadDecoder, success_decoder),
        error_payload_decoder=cast(PayloadDecoder, error_decoder),
        transport=cast(Transport, transport),
        authorization_handler_resolver=cast(
            AuthorizationHandlerResolver,
            authorization_resolver,
        ),
        authorization_handlers=(
            cast(AuthorizationHandler, first_handler),
            cast(AuthorizationHandler, second_handler),
        ),
        capability_resolution=capability_resolution,
    )
    return snapshot, (
        integration_plan,
        component_selection,
        resource_limits,
        adapter,
        access_resolver,
        encoder,
        success_decoder,
        error_decoder,
        transport,
        authorization_resolver,
        first_handler,
        second_handler,
        capability_resolution,
    )


def test_execution_snapshot_preserves_every_resolved_value_and_instance() -> None:
    """Retain exact aggregate values, components, and candidate order."""
    snapshot, values = _complete_snapshot()

    # Direct identity proves construction does not repeat integration, selection,
    # capability resolution, default insertion, or component reconstruction.
    assert snapshot.integration_plan is values[0]
    assert snapshot.component_selection is values[1]
    assert snapshot.resource_limits is values[2]
    assert snapshot.task_protocol_adapter is values[3]
    assert snapshot.service_access_resolver is values[4]
    assert snapshot.payload_encoder is values[5]
    assert snapshot.success_payload_decoder is values[6]
    assert snapshot.error_payload_decoder is values[7]
    assert snapshot.transport is values[8]
    assert snapshot.authorization_handler_resolver is values[9]
    assert snapshot.authorization_handlers[0] is values[10]
    assert snapshot.authorization_handlers[1] is values[11]
    assert snapshot.capability_resolution is values[12]


def test_execution_snapshot_is_frozen_slotted_and_candidate_immutable() -> None:
    """Prevent component replacement and candidate membership mutation."""
    snapshot, values = _complete_snapshot()

    # Frozen fields and tuple membership keep one interaction isolated from later
    # Client, plugin, or caller configuration changes.
    try:
        snapshot.__setattr__("transport", values[3])
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Expected execution snapshot mutation rejection.")
    assert isinstance(snapshot.authorization_handlers, tuple)
    assert snapshot.authorization_handlers == (values[10], values[11])
    assert not hasattr(snapshot.authorization_handlers, "append")
    assert not hasattr(snapshot, "__dict__")


def test_execution_snapshot_has_exact_initial_field_surface() -> None:
    """Expose every required initial field with its precise annotation."""
    annotations = get_type_hints(InteractionExecutionComponents)

    # Declaration order follows completed planning and the unary execution chain;
    # every single-value execution role is non-optional in the final snapshot.
    assert tuple(field.name for field in fields(InteractionExecutionComponents)) == (
        "integration_plan",
        "component_selection",
        "resource_limits",
        "task_protocol_adapter",
        "service_access_resolver",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
        "authorization_handler_resolver",
        "authorization_handlers",
        "capability_resolution",
    )
    assert annotations == {
        "integration_plan": ModelIntegrationPlan,
        "component_selection": ComponentSelectionResolution,
        "resource_limits": ResolvedInteractionResourceLimits,
        "task_protocol_adapter": TaskProtocolAdapter,
        "service_access_resolver": ServiceAccessResolver,
        "payload_encoder": PayloadEncoder,
        "success_payload_decoder": PayloadDecoder,
        "error_payload_decoder": PayloadDecoder,
        "transport": Transport,
        "authorization_handler_resolver": AuthorizationHandlerResolver,
        "authorization_handlers": tuple[AuthorizationHandler, ...],
        "capability_resolution": CapabilityResolution,
    }


def test_execution_snapshot_requires_every_constructor_argument() -> None:
    """Disallow partial snapshots and hidden defaults for completed results."""
    signature = inspect.signature(InteractionExecutionComponents)

    # Even empty candidate and resolution values must be supplied explicitly by
    # the later factory, proving it completed every prerequisite stage.
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    assert all(
        parameter.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        for parameter in signature.parameters.values()
    )


def test_execution_snapshot_excludes_configuration_and_future_roles() -> None:
    """Avoid retaining unresolved configuration or inactive feature fields."""
    snapshot, _ = _complete_snapshot()

    # The snapshot contains selected executable values, not source layers,
    # monitoring options, model resolution inputs, or future mode components.
    for absent_field in (
        "runtime_components",
        "client_components",
        "interaction_components",
        "model_integration_resolver",
        "event_payload_decoder",
        "outgoing_payload_encoder",
        "streaming_transport",
        "client_streaming_transport",
        "duplex_transport",
        "stream_framer",
        "stream_event_mapper",
        "stream_result_accumulator",
        "outgoing_event_mapper",
        "operation_protocol_adapter",
        "artifact_readers",
        "artifact_uploaders",
        "artifact_transformers",
        "artifact_resolver",
        "artifact_operation_executor",
        "capability_requirement_collectors",
        "capability_providers",
        "monitors",
        "credential_source",
    ):
        assert not hasattr(snapshot, absent_field)


def test_execution_snapshot_exposes_no_lookup_or_execution_api() -> None:
    """Keep the snapshot a typed carrier rather than a service locator."""
    snapshot, _ = _complete_snapshot()

    # Resolution and execution remain owned by later fixed Runtime stages; no
    # generic bag or management method can bypass the explicit field contract.
    for forbidden_member in (
        "component_id",
        "component_ids",
        "registry",
        "bindings",
        "additional",
        "roles",
        "register",
        "add",
        "remove",
        "lookup",
        "resolve",
        "merge",
        "select",
        "execute",
        "send",
    ):
        assert not hasattr(snapshot, forbidden_member)
