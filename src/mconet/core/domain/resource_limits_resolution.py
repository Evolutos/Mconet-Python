"""Per-field resolution for interaction byte resource limits."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.interaction_resource_limits import InteractionResourceLimits
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.domain.resource_limits_validation import validate_resource_limits


def resolve_resource_limits(
    sdk_defaults: ResolvedInteractionResourceLimits,
    *,
    client_limits: InteractionResourceLimits | None = None,
    interaction_limits: InteractionResourceLimits | None = None,
) -> ResolvedInteractionResourceLimits:
    """Resolve complete limits from interaction, client, and SDK layers.

    Each field independently uses the highest-priority explicit value:
    interaction, then client, then the complete SDK safe defaults. Every layer
    is validated before merging so an overridden invalid value cannot escape
    configuration validation.

    Args:
        sdk_defaults: Complete finite defaults selected by the SDK composition
            root.
        client_limits: Optional reusable client-level field overrides.
        interaction_limits: Optional overrides for only the current interaction.

    Returns:
        An immutable value containing all three resolved byte limits.

    Raises:
        TypeError: If a layer is not its declared nominal resource-limit type.
        ValueError: If any supplied value is nonpositive or outside signed
            64-bit range.
    """
    defaults = cast(object, sdk_defaults)
    # Require a complete default layer rather than accepting optional input that
    # could leave the resolved result missing or implicitly unlimited.
    if not isinstance(defaults, ResolvedInteractionResourceLimits):
        raise TypeError("sdk_defaults must be ResolvedInteractionResourceLimits.")
    validate_resource_limits(defaults)

    client = _validate_optional_layer(client_limits, "client_limits")
    interaction = _validate_optional_layer(
        interaction_limits,
        "interaction_limits",
    )

    # Resolve each limit independently. A value present in one field never
    # promotes the other fields from the same layer over lower-priority values.
    resolved = ResolvedInteractionResourceLimits(
        max_response_body_bytes=_resolve_field(
            interaction.max_response_body_bytes if interaction is not None else None,
            client.max_response_body_bytes if client is not None else None,
            defaults.max_response_body_bytes,
        ),
        max_streaming_error_body_bytes=_resolve_field(
            (
                interaction.max_streaming_error_body_bytes
                if interaction is not None
                else None
            ),
            (client.max_streaming_error_body_bytes if client is not None else None),
            defaults.max_streaming_error_body_bytes,
        ),
        max_frame_bytes=_resolve_field(
            interaction.max_frame_bytes if interaction is not None else None,
            client.max_frame_bytes if client is not None else None,
            defaults.max_frame_bytes,
        ),
    )
    # Validate the assembled object as a final invariant check before consumers
    # share it, even though every source layer has already passed validation.
    return validate_resource_limits(resolved)


def _validate_optional_layer(
    limits: InteractionResourceLimits | None,
    field_name: str,
) -> InteractionResourceLimits | None:
    """Validate one optional unresolved override layer without resolving it."""
    candidate = cast(object, limits)
    # None means that the entire layer is absent. A present layer must use the
    # nominal unresolved type so resolved defaults cannot occupy the wrong tier.
    if candidate is None:
        return None
    if not isinstance(candidate, InteractionResourceLimits):
        raise TypeError(f"{field_name} must be InteractionResourceLimits or None.")
    return validate_resource_limits(candidate)


def _resolve_field(
    interaction_value: int | None,
    client_value: int | None,
    sdk_default: int,
) -> int:
    """Select one byte limit using the fixed per-field priority order."""
    # Presence, rather than truthiness, determines an override. Validation has
    # already rejected zero, but an explicit None must still fall through.
    if interaction_value is not None:
        return interaction_value
    if client_value is not None:
        return client_value
    return sdk_default
