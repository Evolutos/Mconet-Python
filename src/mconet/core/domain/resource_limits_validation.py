"""Semantic validation for unresolved and resolved interaction byte limits."""

from __future__ import annotations

from typing import cast, overload

from mconet.core.domain.interaction_resource_limits import InteractionResourceLimits
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)

_MIN_SIGNED_INT64 = -(1 << 63)
_MAX_SIGNED_INT64 = (1 << 63) - 1


@overload
def validate_resource_limits(
    limits: InteractionResourceLimits,
) -> InteractionResourceLimits:
    """Preserve the unresolved input type for static callers."""
    ...


@overload
def validate_resource_limits(
    limits: ResolvedInteractionResourceLimits,
) -> ResolvedInteractionResourceLimits:
    """Preserve the resolved input type for static callers."""
    ...


def validate_resource_limits(
    limits: InteractionResourceLimits | ResolvedInteractionResourceLimits,
) -> InteractionResourceLimits | ResolvedInteractionResourceLimits:
    """Validate positive portable integers without resolving absent fields.

    Args:
        limits: Unresolved optional limits or a complete resolved limit value.

    Returns:
        The same immutable limit object after every present field is valid.

    Raises:
        TypeError: If ``limits`` is not a supported nominal limit value.
        ValueError: If a present field is outside signed 64-bit range or is not
            positive.
    """
    candidate = cast(object, limits)
    # Accept only the two domain values owned by this validation boundary. An
    # arbitrary attribute-compatible object could bypass constructor type rules.
    if not isinstance(
        candidate,
        (InteractionResourceLimits, ResolvedInteractionResourceLimits),
    ):
        raise TypeError(
            "limits must be InteractionResourceLimits or "
            "ResolvedInteractionResourceLimits."
        )

    # Both values expose the same field names. Optional None values are skipped
    # without resolution so the next configuration layer can still provide them.
    for field_name, value in (
        ("max_response_body_bytes", candidate.max_response_body_bytes),
        (
            "max_streaming_error_body_bytes",
            candidate.max_streaming_error_body_bytes,
        ),
        ("max_frame_bytes", candidate.max_frame_bytes),
    ):
        if value is None:
            continue

        # Check portable storage before positivity so values beyond either Int64
        # boundary receive an overflow diagnostic rather than a sign diagnostic.
        if not _MIN_SIGNED_INT64 <= value <= _MAX_SIGNED_INT64:
            raise ValueError(
                f"Resource limit {field_name} must fit signed 64-bit range."
            )
        # Zero cannot limit resource use, and negative sentinel values must not
        # become an implicit unlimited mode in any downstream consumer.
        if value <= 0:
            raise ValueError(f"Resource limit {field_name} must be positive.")

    return candidate
