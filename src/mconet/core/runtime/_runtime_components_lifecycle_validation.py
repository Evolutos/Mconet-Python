"""Lifecycle validation for components stored on a reusable client."""

from __future__ import annotations

import inspect
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_ownership import ComponentOwnership
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.runtime_components import RuntimeComponents

_INVALID_COMPONENT_CONFIGURATION = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_COMPONENT_LIFECYCLE = InteractionPhase(OpenIdentifier("component_lifecycle"))
_INVALID_LIFECYCLE_CODE = "invalid_component_lifecycle"
_BUILTIN_OWNER = "builtin"
_APPLICATION_OWNER = "application"
_STANDARD_OWNERS = frozenset((_BUILTIN_OWNER, _APPLICATION_OWNER))
_REUSABLE_METHODS = (
    "encode",
    "decode",
    "send",
    "resolve",
    "apply",
    "supports",
    "build_request",
    "parse_response",
)
_SINGLE_FIELDS = (
    "model_integration_resolver",
    "task_protocol_adapter",
    "service_access_resolver",
    "payload_encoder",
    "success_payload_decoder",
    "error_payload_decoder",
    "transport",
    "authorization_handler_resolver",
)


def validate_runtime_components_lifecycle(
    components: RuntimeComponents,
    owner: ComponentOwnership,
) -> RuntimeComponents:
    """Reject a client component whose lifecycle form or owner is illegal.

    Reusable stateless instances and resource components with an asynchronous
    ``close`` may be stored for either standard owner. ``builtin`` means the
    SDK created the component. ``application`` means the caller injected it and
    will keep it after the client closes. Descriptor ``source`` is not
    ownership and is ignored.

    A per-interaction state instance, such as a framer or accumulator, cannot
    be stored on the client. Its factory is also rejected here because the R1
    carrier has no factory field. A synchronous ``close`` does not satisfy the
    asynchronous lifecycle contract. This function does not call ``close``,
    ``create``, or any behavior method.

    Args:
        components: Direct-injection carrier that a client would retain.
        owner: Lifecycle owner already chosen for this carrier.

    Returns:
        The same carrier when every present component can be retained.

    Raises:
        TypeError: If the carrier, owner, or a present component has an invalid
            nominal shape.
        ModelInteractionError: If the owner is not a standard lifecycle owner,
            a stateful instance or factory is stored, or ``close`` is not
            asynchronous. The code is ``invalid_component_lifecycle``.
    """
    candidate = cast(object, components)
    owner_value = cast(object, owner)
    if not isinstance(candidate, RuntimeComponents):
        raise TypeError("components must be a RuntimeComponents.")
    if not isinstance(owner_value, ComponentOwnership):
        raise TypeError("owner must be a ComponentOwnership.")
    # Only the two standard owners have a defined close decision. An extension
    # value must fail here instead of being treated as application or builtin.
    if owner_value.id.value not in _STANDARD_OWNERS:
        raise _lifecycle_error(
            "Component lifecycle owner must be builtin or application."
        )

    for field_name in _SINGLE_FIELDS:
        value = cast(object, getattr(candidate, field_name))
        if value is None:
            continue
        _validate_component(value, field_name)

    handlers = cast(object, candidate.authorization_handlers)
    if not isinstance(handlers, tuple):
        raise TypeError("authorization_handlers must be a tuple.")
    for handler in cast(tuple[object, ...], handlers):
        _validate_component(handler, "authorization_handlers")
    return candidate


def _validate_component(value: object, field_name: str) -> None:
    """Require one reusable component and reject client-stored interaction state."""
    if not isinstance(value, RuntimeComponent):
        raise TypeError(f"{field_name} must implement RuntimeComponent.")
    descriptor = cast(object, value.descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(f"{field_name} descriptor must be a ComponentDescriptor.")

    # State is identified from the architecture's operations. Reading the
    # attribute does not invoke it, so an illegal component cannot run.
    if _is_interaction_state_instance(value):
        raise _lifecycle_error(
            "A stateful instance cannot be stored in client components."
        )
    if _is_unbound_state_factory(value):
        raise _lifecycle_error(
            "A stateful factory cannot occupy a reusable instance field."
        )

    close = getattr(value, "close", None)
    # Absence is the stateless reusable form. A present close must be the
    # asynchronous resource operation; a synchronous method is the wrong contract.
    if close is None:
        return
    if not inspect.iscoroutinefunction(close):
        raise _lifecycle_error(
            "Component close must be an asynchronous lifecycle operation."
        )


def _is_interaction_state_instance(value: object) -> bool:
    """Return whether the object is one interaction's mutable state."""
    # A factory exposes create and is classified separately. Frame is the framer
    # instance operation. Append together with finalize is the accumulator.
    if callable(getattr(value, "create", None)):
        return False
    if callable(getattr(value, "frame", None)):
        return True
    return callable(getattr(value, "append", None)) and callable(
        getattr(value, "finalize", None)
    )


def _is_unbound_state_factory(value: object) -> bool:
    """Return whether the object is a state factory stored as an instance."""
    if not callable(getattr(value, "create", None)):
        return False
    # A reusable role may expose an unrelated helper named create. Only an
    # object with no R1 behavior operation is a state factory in an instance field.
    for name in _REUSABLE_METHODS:
        if callable(getattr(value, name, None)):
            return False
    return True


def _lifecycle_error(message: str) -> ModelInteractionError:
    """Create the stable failure for one illegal client lifecycle."""
    # The message is chosen by the caller and must not include component names,
    # ports, or resource identifiers.
    return ModelInteractionError(
        category=_INVALID_COMPONENT_CONFIGURATION,
        phase=_COMPONENT_LIFECYCLE,
        code=_INVALID_LIFECYCLE_CODE,
        message=message,
    )
