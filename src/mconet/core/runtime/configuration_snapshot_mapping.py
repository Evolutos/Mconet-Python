"""Redacted mapping from resolved configuration to a safe scalar snapshot."""

from __future__ import annotations

from mconet.core.runtime.resolved_configuration_validation import (
    validate_resolved_configuration,
)
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.core.runtime.safe_configuration_snapshot import (
    SafeConfigurationSnapshot,
)


def map_safe_configuration_snapshot(
    configuration: ResolvedInteractionConfiguration,
) -> SafeConfigurationSnapshot:
    """Validate and map resolved configuration to its non-sensitive scalar shape.

    Args:
        configuration: Complete immutable configuration selected for interaction.

    Returns:
        A new immutable snapshot containing only approved scalar facts.

    Raises:
        TypeError: If the configuration or a nested field violates its runtime
            contract.
        ValueError: If target, access, or resource-limit semantics are invalid.

    Notes:
        Validation first inspects target/access structure and semantics, including
        the opaque authorization kind, but never reads credential contents. The
        mapping stage copies no endpoint/access payload, model metadata/extension,
        cancellation state/reason, or arbitrary custom object representation.
    """
    validated = validate_resolved_configuration(configuration)
    target = validated.target
    model = target.model
    resource_limits = validated.resource_limits

    # Only identifiers and model/deployment names explicitly approved for
    # monitoring cross the target boundary. Display data, metadata, extensions,
    # and the custom target object's representation are never copied.
    service_id = target.service_id.value
    protocol_id = target.protocol_id.value
    model_name = model.name
    deployment_id = target.deployment_id

    # After validation, access and cancellation are represented only by presence.
    # The mapping stage does not copy endpoint, authorization, headers/query,
    # credentials, signal state, reason, or subscriptions into the snapshot.
    service_access_configured = validated.service_access is not None
    cancellation_configured = validated.cancellation_signal is not None

    # CompatibilityPolicy and resolved limits are immutable validated values;
    # copy only their JSON-scalar contents into the closed snapshot type.
    return SafeConfigurationSnapshot(
        service_id=service_id,
        protocol_id=protocol_id,
        model_name=model_name,
        deployment_id=deployment_id,
        service_access_configured=service_access_configured,
        compatibility_policy=validated.compatibility_policy.mode.value,
        max_response_body_bytes=resource_limits.max_response_body_bytes,
        max_streaming_error_body_bytes=(resource_limits.max_streaming_error_body_bytes),
        max_frame_bytes=resource_limits.max_frame_bytes,
        cancellation_configured=cancellation_configured,
    )
