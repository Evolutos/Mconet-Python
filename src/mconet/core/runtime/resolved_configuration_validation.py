"""Pre-I/O semantic validation for resolved interaction configuration."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.model_target_validation import validate_model_target
from mconet.core.domain.resource_limits_validation import validate_resource_limits
from mconet.core.domain.service_access_validation import validate_service_access
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)


def validate_resolved_configuration(
    configuration: ResolvedInteractionConfiguration,
) -> ResolvedInteractionConfiguration:
    """Validate every semantic configuration boundary before downstream work.

    Args:
        configuration: Complete immutable result of configuration merging.

    Returns:
        The same resolved configuration after all applicable validators succeed.

    Raises:
        TypeError: If the input is not the internal resolved configuration type,
            or if a nested target/access field violates its runtime contract.
        ValueError: If model target semantics, endpoint/access semantics, or any
            complete resource limit is invalid.

    Notes:
        Validation is side-effect free. It does not resolve access fields, read
        authorization credentials, inspect cancellation state, create snapshots,
        select components, or perform transport I/O.
    """
    candidate = cast(object, configuration)
    # Require the nominal internal carrier before reading nested fields. This
    # prevents an arbitrary attribute-compatible object from bypassing the
    # completeness checks established by ResolvedInteractionConfiguration.
    if not isinstance(candidate, ResolvedInteractionConfiguration):
        raise TypeError("configuration must be ResolvedInteractionConfiguration.")

    # Validate target first because model selection is required for every later
    # integration, access, component, or transport operation. The shared target
    # validator also delegates required model-name and extension validation.
    validate_model_target(candidate.target)

    # Access may remain absent until a later integration contributes defaults.
    # A present object is validated without resolving fields or reading opaque
    # Authorization credential data.
    if candidate.service_access is not None:
        validate_service_access(candidate.service_access)

    # The resolved object contains all three limits. Reuse the shared validator
    # so positivity and signed Int64 portability remain identical for every path.
    validate_resource_limits(candidate.resource_limits)

    # Preserve identity and immutability; downstream consumers share the exact
    # configuration that passed validation rather than a normalized copy.
    return candidate
