"""Shape, ownership, and immutability tests for direct runtime components."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast, get_type_hints

from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    ComponentDescriptor,
    ModelIntegrationResolver,
    PayloadDecoder,
    PayloadEncoder,
    RuntimeComponents,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
)


@dataclass(frozen=True, slots=True)
class _Component:
    """Distinguishable component-shaped fixture for carrier identity tests."""

    descriptor: ComponentDescriptor
    """Immutable diagnostic metadata shared by all runtime behavior protocols."""


def _component(name: str) -> _Component:
    """Build one concrete component-shaped fixture with a unique label."""
    # The carrier preserves concrete object identity; behavior methods are
    # intentionally outside this value-shape test and validated in later gates.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _complete_components() -> tuple[
    RuntimeComponents,
    tuple[_Component, ...],
]:
    """Build a fully populated carrier and retain every concrete fixture."""
    # Distinct instances make field swaps, candidate reordering, ID replacement,
    # and hidden default construction observable without running component logic.
    integration_resolver = _component("Integration resolver")
    adapter = _component("Task adapter")
    access_resolver = _component("Access resolver")
    encoder = _component("Payload encoder")
    success_decoder = _component("Success decoder")
    error_decoder = _component("Error decoder")
    transport = _component("Transport")
    authorization_resolver = _component("Authorization resolver")
    first_handler = _component("First authorization handler")
    second_handler = _component("Second authorization handler")

    components = RuntimeComponents(
        model_integration_resolver=cast(
            ModelIntegrationResolver,
            integration_resolver,
        ),
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
    )
    return components, (
        integration_resolver,
        adapter,
        access_resolver,
        encoder,
        success_decoder,
        error_decoder,
        transport,
        authorization_resolver,
        first_handler,
        second_handler,
    )


def test_runtime_components_defaults_to_no_direct_overrides() -> None:
    """Represent an empty configuration layer without placeholder components."""
    components = RuntimeComponents()

    # None preserves absence for every single role, while an empty tuple adds no
    # authorization candidates and needs no mutable default allocation.
    assert components.model_integration_resolver is None
    assert components.task_protocol_adapter is None
    assert components.service_access_resolver is None
    assert components.payload_encoder is None
    assert components.success_payload_decoder is None
    assert components.error_payload_decoder is None
    assert components.transport is None
    assert components.authorization_handler_resolver is None
    assert components.authorization_handlers == ()


def test_runtime_components_preserves_every_injected_instance_and_order() -> None:
    """Retain exact single components and ordered authorization candidates."""
    components, instances = _complete_components()

    # Direct references prove the carrier performs no registry lookup, component
    # reconstruction, role inference, candidate sorting, or default insertion.
    assert components.model_integration_resolver is instances[0]
    assert components.task_protocol_adapter is instances[1]
    assert components.service_access_resolver is instances[2]
    assert components.payload_encoder is instances[3]
    assert components.success_payload_decoder is instances[4]
    assert components.error_payload_decoder is instances[5]
    assert components.transport is instances[6]
    assert components.authorization_handler_resolver is instances[7]
    assert components.authorization_handlers[0] is instances[8]
    assert components.authorization_handlers[1] is instances[9]


def test_runtime_components_is_an_immutable_slotted_snapshot() -> None:
    """Reject field replacement and authorization candidate membership changes."""
    components, instances = _complete_components()

    # Frozen fields prevent a configuration layer from changing after capture;
    # tuple membership remains fixed while retaining exact handler instances.
    try:
        components.__setattr__("transport", None)
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Expected RuntimeComponents field mutation rejection.")
    assert isinstance(components.authorization_handlers, tuple)
    assert components.authorization_handlers == (instances[8], instances[9])
    assert not hasattr(components.authorization_handlers, "append")
    assert not hasattr(components, "__dict__")


def test_runtime_components_has_exact_initial_field_surface() -> None:
    """Expose only implemented initial behavior roles with precise annotations."""
    annotations = get_type_hints(RuntimeComponents)

    # Declaration order follows integration and execution resolution flow; every
    # field names one semantic role instead of accepting an untyped role map.
    assert tuple(field.name for field in fields(RuntimeComponents)) == (
        "model_integration_resolver",
        "task_protocol_adapter",
        "service_access_resolver",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
        "authorization_handler_resolver",
        "authorization_handlers",
    )
    assert annotations == {
        "model_integration_resolver": ModelIntegrationResolver | None,
        "task_protocol_adapter": TaskProtocolAdapter | None,
        "service_access_resolver": ServiceAccessResolver | None,
        "payload_encoder": PayloadEncoder | None,
        "success_payload_decoder": PayloadDecoder | None,
        "error_payload_decoder": PayloadDecoder | None,
        "transport": Transport | None,
        "authorization_handler_resolver": AuthorizationHandlerResolver | None,
        "authorization_handlers": tuple[AuthorizationHandler, ...],
    }


def test_runtime_components_excludes_unimplemented_and_separate_roles() -> None:
    """Avoid publishing inert future fields or unrelated monitoring options."""
    components = RuntimeComponents()

    # Streaming, artifact, operation, capability-provider, and monitoring fields
    # enter only with complete contracts or their dedicated option containers.
    for absent_field in (
        "event_payload_decoder",
        "outgoing_payload_encoder",
        "streaming_transport",
        "client_streaming_transport",
        "duplex_transport",
        "stream_framer_factory",
        "stream_event_mapper",
        "stream_result_accumulator_factory",
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
        assert not hasattr(components, absent_field)


def test_runtime_components_excludes_ids_registries_and_generic_role_bags() -> None:
    """Require direct typed instances instead of deferred component lookup."""
    components = RuntimeComponents()

    # No generic escape hatch can bypass the explicit stable role vocabulary or
    # reintroduce business-writable registration and component-ID resolution.
    for forbidden_member in (
        "component_id",
        "component_ids",
        "registry",
        "bindings",
        "additional",
        "components",
        "roles",
        "register",
        "add",
        "remove",
        "lookup",
        "resolve",
        "merge",
        "select",
    ):
        assert not hasattr(components, forbidden_member)


def test_runtime_components_constructor_has_explicit_keyword_surface() -> None:
    """Keep direct injection discoverable without variadic extension channels."""
    signature = inspect.signature(RuntimeComponents)

    # Generated construction exposes every typed role directly and has no
    # positional catch-all, keyword bag, registry key, or component-ID argument.
    assert tuple(signature.parameters) == (
        "model_integration_resolver",
        "task_protocol_adapter",
        "service_access_resolver",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
        "authorization_handler_resolver",
        "authorization_handlers",
    )
    assert all(
        parameter.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        for parameter in signature.parameters.values()
    )
