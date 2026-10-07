"""Deterministic lifecycle ownership for concrete runtime component instances."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentOwnership,
    RuntimeComponent,
    RuntimeComponents,
)

_BUILTIN_OWNERSHIP = ComponentOwnership(OpenIdentifier("builtin"))
_APPLICATION_OWNERSHIP = ComponentOwnership(OpenIdentifier("application"))


def determine_component_ownership(
    component: RuntimeComponent,
    *,
    interaction_components: RuntimeComponents | None,
    client_components: RuntimeComponents | None,
    sdk_defaults: RuntimeComponents,
) -> ComponentOwnership:
    """Return lifecycle ownership from exact direct-injection membership.

    An instance present in either direct application layer is application-owned,
    even when the same object also appears among SDK defaults. Otherwise, only
    exact identity membership in ``sdk_defaults`` establishes builtin ownership.
    Every unlisted instance, including one supplied by an integration binding or
    plugin, defaults safely to application ownership because the SDK cannot prove
    that it created or owns that resource.

    All supplied RuntimeComponents fields are validated before membership is
    evaluated, including shadowed and unrelated roles. Matching uses ``is`` and
    never component equality, descriptor values, names, versions, source labels,
    capability IDs, or behavior calls. The function neither associates ownership
    with the component nor closes, wraps, copies, registers, or mutates it.

    Returns:
        The immutable ``builtin`` or ``application`` ownership value.

    Raises:
        TypeError: If the target, a component layer, a candidate collection, or
            candidate metadata violates its nominal immutable boundary.
    """
    target = _validate_component(component, "component")
    interaction = _component_instances(
        interaction_components,
        "interaction_components",
        optional=True,
    )
    client = _component_instances(
        client_components,
        "client_components",
        optional=True,
    )
    defaults = _component_instances(
        sdk_defaults,
        "sdk_defaults",
        optional=False,
    )

    # Direct injection is an explicit application ownership decision. Evaluate
    # both application scopes before SDK membership so aliasing cannot transfer
    # a caller-supplied instance back to SDK lifecycle control accidentally.
    application_instances = (*interaction, *client)
    if any(target is candidate for candidate in application_instances):
        return _APPLICATION_OWNERSHIP

    # Only the exact instance retained by SDK defaults is proven SDK-created and
    # eligible for later builtin-owned release. Equal metadata or values do not.
    if any(target is candidate for candidate in defaults):
        return _BUILTIN_OWNERSHIP

    # Binding, plugin, factory, and otherwise untracked origins stay externally
    # owned by default. This conservative result prevents accidental close calls.
    return _APPLICATION_OWNERSHIP


def _component_instances(
    value: RuntimeComponents | None,
    parameter_name: str,
    *,
    optional: bool,
) -> tuple[RuntimeComponent, ...]:
    """Validate one component carrier and return every exact stored instance."""
    candidate = cast(object, value)

    # None means an absent direct application layer only. SDK defaults are a
    # required creation-scope fact and cannot be replaced by implicit emptiness.
    if candidate is None:
        if optional:
            return ()
        raise TypeError(f"{parameter_name} must be a RuntimeComponents.")
    if not isinstance(candidate, RuntimeComponents):
        suffix = " or None" if optional else ""
        raise TypeError(f"{parameter_name} must be a RuntimeComponents{suffix}.")

    handlers = cast(object, candidate.authorization_handlers)
    # Candidate membership must already be immutable before ownership can be
    # retained by a reusable Client; copying a list would hide caller mutation.
    if not isinstance(handlers, tuple):
        raise TypeError(f"{parameter_name} authorization_handlers must be a tuple.")

    raw_components: tuple[object | None, ...] = (
        candidate.model_integration_resolver,
        candidate.task_protocol_adapter,
        candidate.service_access_resolver,
        candidate.payload_encoder,
        candidate.success_payload_decoder,
        candidate.error_payload_decoder,
        candidate.transport,
        candidate.authorization_handler_resolver,
        *cast(tuple[object, ...], handlers),
    )

    validated: list[RuntimeComponent] = []
    for item in raw_components:
        # None is the explicit absence value for single roles. Every present
        # single role and list member must satisfy the same metadata boundary.
        if item is None:
            continue
        validated.append(_validate_component(item, parameter_name))

    # A fresh tuple freezes only this local membership view. It preserves every
    # exact component object, duplicate, and source-field order without mutation.
    return tuple(validated)


def _validate_component(value: object, field_name: str) -> RuntimeComponent:
    """Require one runtime component with nominal descriptor metadata."""
    # Structural conformance admits SDK, plugin, and application implementations
    # without inheritance, while rejecting unrelated candidate objects.
    if not isinstance(value, RuntimeComponent):
        raise TypeError(f"{field_name} must implement RuntimeComponent.")

    # Runtime protocol checks prove property presence only. A nominal descriptor
    # prevents dynamic values from injecting source or identity look-alikes.
    descriptor = cast(object, value.descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(f"{field_name} descriptor must be a ComponentDescriptor.")
    return value
