"""SPI validation for directly injected runtime components."""

from __future__ import annotations

from typing import cast

from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.authorization_handler_resolver import (
    AuthorizationHandlerResolver,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.model_integration_resolver import ModelIntegrationResolver
from mconet.core.spi.payload_decoder import PayloadDecoder
from mconet.core.spi.payload_encoder import PayloadEncoder
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.runtime_components import RuntimeComponents
from mconet.core.spi.service_access_resolver import ServiceAccessResolver
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter
from mconet.core.spi.transport import Transport

_SINGLE_ROLES: tuple[tuple[str, type[object]], ...] = (
    ("model_integration_resolver", ModelIntegrationResolver),
    ("task_protocol_adapter", TaskProtocolAdapter),
    ("service_access_resolver", ServiceAccessResolver),
    ("payload_encoder", PayloadEncoder),
    ("success_payload_decoder", PayloadDecoder),
    ("error_payload_decoder", PayloadDecoder),
    ("transport", Transport),
    ("authorization_handler_resolver", AuthorizationHandlerResolver),
)


def validate_runtime_components_spi(
    components: RuntimeComponents,
) -> RuntimeComponents:
    """Require every present component to implement its field protocol.

    ``None`` leaves a single role unset. An empty handler tuple contributes no
    candidates. A present value must implement that field's behavior protocol,
    including ``RuntimeComponent``, and expose a nominal
    ``ComponentDescriptor``. This check does not compare type-contract ports,
    capabilities, or lifecycle ownership, and it does not call component
    behavior.

    Args:
        components: One direct-injection carrier from client or interaction
            configuration.

    Returns:
        The same carrier when every present instance matches its field.

    Raises:
        TypeError: If the carrier, a handler collection, or a present instance
            does not match the protocol declared by its field.
    """
    candidate = cast(object, components)
    if not isinstance(candidate, RuntimeComponents):
        raise TypeError("components must be a RuntimeComponents.")

    for field_name, protocol in _SINGLE_ROLES:
        # Absent roles are explicit non-overrides. Only a supplied instance is
        # required to satisfy the protocol named by that field.
        value = cast(object, getattr(candidate, field_name))
        if value is None:
            continue
        _validate_behavior(value, protocol, field_name)

    handlers = cast(object, candidate.authorization_handlers)
    # A list would let a later caller mutate the candidate set. The declared
    # carrier stores an immutable tuple before any handler protocol is checked.
    if not isinstance(handlers, tuple):
        raise TypeError("authorization_handlers must be a tuple.")
    for handler in cast(tuple[object, ...], handlers):
        _validate_behavior(handler, AuthorizationHandler, "authorization_handlers")

    # Identity is preserved so a later client can retain the caller's carrier
    # without copying or reordering its instances.
    return candidate


def _validate_behavior(value: object, protocol: type[object], field_name: str) -> None:
    """Require one structural behavior instance and its nominal descriptor."""
    # Runtime-checkable protocols admit ordinary classes. A descriptor-only
    # object, or an object built for a different role, fails this field.
    if not isinstance(value, protocol):
        raise TypeError(f"{field_name} must implement the declared behavior protocol.")

    # Member presence does not prove the descriptor type. Reject a stand-in
    # before client construction treats the instance as injectable metadata.
    component = cast(RuntimeComponent, value)
    descriptor = cast(object, component.descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(f"{field_name} descriptor must be a ComponentDescriptor.")
