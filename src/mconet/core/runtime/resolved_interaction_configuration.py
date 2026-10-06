"""Internal immutable result of interaction configuration merging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.domain.service_access import ServiceAccess


@dataclass(frozen=True, slots=True)
class ResolvedInteractionConfiguration:
    """Carry the complete immutable result of configuration-layer selection.

    Target, compatibility policy, and resource limits are concrete. Service
    access may remain absent until the selected integration contributes its
    default through the later ServiceAccessResolver. Cancellation is optional by
    contract but its field is explicit. This object stores references only and
    never materializes authorization plaintext or a secret snapshot.

    The selected ServiceAccess remains unresolved. It is neither a
    ResolvedServiceAccess nor a replacement for passing all four original access
    sources to the later field-level ServiceAccessResolver.

    The type is intentionally internal and contains no runtime components,
    monitors, normalizers, or public option containers.
    """

    target: ModelTarget
    """The selected interaction target."""

    service_access: ServiceAccess | None
    """The winning whole access input, not a field-merged access result."""

    compatibility_policy: CompatibilityPolicy
    """The selected compatibility strategy."""

    resource_limits: ResolvedInteractionResourceLimits
    """The complete finite byte limits shared by downstream consumers."""

    cancellation_signal: CancellationSignal | None
    """The optional signal owned by this single interaction."""

    def __post_init__(self) -> None:
        """Require complete fields to satisfy their nominal storage contracts."""
        target = cast(object, self.target)
        service_access = cast(object, self.service_access)
        compatibility_policy = cast(object, self.compatibility_policy)
        resource_limits = cast(object, self.resource_limits)
        cancellation_signal = cast(object, self.cancellation_signal)

        # A target is mandatory after source selection, but its identifier,
        # descriptor, and extension semantics remain owned by the later validator.
        if not isinstance(target, ModelTarget):
            raise TypeError(
                "ResolvedInteractionConfiguration target must implement ModelTarget."
            )

        # Access absence remains explicit because integration resolution can
        # contribute its default later. A present custom access stays structural.
        if service_access is not None and not isinstance(
            service_access,
            ServiceAccess,
        ):
            raise TypeError(
                "ResolvedInteractionConfiguration service_access must implement "
                "ServiceAccess or be None."
            )

        # Policy and limits must already have concrete resolved value types;
        # semantic policy behavior and numeric validation are not repeated here.
        if not isinstance(compatibility_policy, CompatibilityPolicy):
            raise TypeError(
                "ResolvedInteractionConfiguration compatibility_policy must be "
                "CompatibilityPolicy."
            )
        if not isinstance(resource_limits, ResolvedInteractionResourceLimits):
            raise TypeError(
                "ResolvedInteractionConfiguration resource_limits must be "
                "ResolvedInteractionResourceLimits."
            )

        # The signal remains a producer-controlled reference. Construction does
        # not inspect its reason, subscribe, request cancellation, or copy state.
        if cancellation_signal is not None and not isinstance(
            cancellation_signal,
            CancellationSignal,
        ):
            raise TypeError(
                "ResolvedInteractionConfiguration cancellation_signal must "
                "implement CancellationSignal or be None."
            )
