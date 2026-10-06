"""Deterministic merging of internal interaction configuration data layers."""

from __future__ import annotations

from typing import TypeVar, cast

from mconet.core.domain.compatibility_policy import default_compatibility_policy
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.domain.resource_limits_resolution import resolve_resource_limits
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)

_Value = TypeVar("_Value")


def merge_interaction_configuration(
    *,
    interaction_layer: InteractionConfigurationLayer,
    request_layer: InteractionConfigurationLayer,
    client_layer: InteractionConfigurationLayer,
    integration_layer: InteractionConfigurationLayer,
    sdk_resource_limits: ResolvedInteractionResourceLimits,
) -> ResolvedInteractionConfiguration:
    """Merge pure configuration data using the fixed per-field source order.

    Args:
        interaction_layer: Explicit values owned by only this interaction.
        request_layer: Values carried by the current model request.
        client_layer: Reusable defaults captured from the client configuration.
        integration_layer: Defaults contributed by the selected integration.
        sdk_resource_limits: Complete finite byte limits from the composition root.

    Returns:
        An immutable configuration containing every required resolved field.

    Raises:
        TypeError: If any source does not use its declared nominal layer type, or
            if a resource-limit layer violates its storage contract.
        ValueError: If neither Request nor Client supplies a target, or if any
            applicable resource-limit value violates its semantic contract.

    Notes:
        This function merges only pure configuration data. Component selection,
        monitor-list merging, semantic Target/Access validation, and safe
        snapshot mapping remain separate runtime steps.

        The selected ``service_access`` is a whole input reference for resolved
        configuration state. This function does not replace the later
        ServiceAccessResolver: callers must retain and pass all four original
        access sources when producing ResolvedServiceAccess field by field.
    """
    interaction = _require_layer(interaction_layer, "interaction_layer")
    request = _require_layer(request_layer, "request_layer")
    client = _require_layer(client_layer, "client_layer")
    integration = _require_layer(integration_layer, "integration_layer")

    # Target has no interaction or integration source. Requiring the selected
    # structural object here makes the resolved carrier complete; its model and
    # identifier semantics remain the responsibility of the later validator.
    target = _first_present(request.target, client.target)
    if target is None:
        raise ValueError("target must be provided by request_layer or client_layer.")

    # Access remains a whole opaque reference at this boundary. Source layers are
    # immutable and stay available to the later four-input ServiceAccessResolver;
    # this selection neither merges fields nor exposes/copies Authorization state.
    service_access = _first_present(
        interaction.service_access,
        request.service_access,
        client.service_access,
        integration.service_access,
    )

    # Compatibility has no Request or integration source. Construct the SDK
    # fallback through its validated public factory only when both overrides are
    # absent, preserving caller objects by identity when one is selected.
    compatibility_policy = _first_present(
        interaction.compatibility_policy,
        client.compatibility_policy,
    )
    if compatibility_policy is None:
        compatibility_policy = default_compatibility_policy()

    # Delegate byte-limit semantics to the shared resolver. It validates every
    # applicable layer and selects each field independently, so one explicit
    # limit cannot promote absent sibling fields from the same source.
    resource_limits = resolve_resource_limits(
        sdk_resource_limits,
        client_limits=client.resource_limits,
        interaction_limits=interaction.resource_limits,
    )

    # Cancellation is scoped to the current interaction. Values accidentally
    # present in reusable or request/integration layers never leak into another
    # execution, and the signal is retained without inspection or subscription.
    cancellation_signal = interaction.cancellation_signal

    # Resolved storage keeps selected structural values by reference and freezes
    # the field set. Construction does not mutate any reusable source layer.
    return ResolvedInteractionConfiguration(
        target=target,
        service_access=service_access,
        compatibility_policy=compatibility_policy,
        resource_limits=resource_limits,
        cancellation_signal=cancellation_signal,
    )


def _require_layer(
    value: InteractionConfigurationLayer,
    field_name: str,
) -> InteractionConfigurationLayer:
    """Require one source to use the internal configuration-layer carrier."""
    candidate = cast(object, value)
    # Nominal checking catches dynamically typed source transposition before the
    # merger reads attributes or reports a misleading missing-field failure.
    if not isinstance(candidate, InteractionConfigurationLayer):
        raise TypeError(f"{field_name} must be InteractionConfigurationLayer.")
    return candidate


def _first_present(*values: _Value | None) -> _Value | None:
    """Return the first non-None value from a highest-to-lowest source sequence."""
    # Presence, not truthiness or equality, defines an override. Structural value
    # objects are returned by identity without normalization, copying, or merging.
    for value in values:
        if value is not None:
            return value
    return None
