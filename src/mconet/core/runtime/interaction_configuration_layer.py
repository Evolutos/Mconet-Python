"""Internal optional data layer used by interaction configuration merging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.interaction_resource_limits import InteractionResourceLimits
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.service_access import ServiceAccess


@dataclass(frozen=True, slots=True)
class InteractionConfigurationLayer:
    """Hold one internal layer of independently overridable configuration.

    Every field may be absent so a later deterministic merger can select data
    values from interaction, request, client, integration, or SDK sources. The
    cancellation signal is populated only for the single-interaction layer. The
    carrier contains no component instances, normalizers, monitoring options, or
    monitors; those belong to their dedicated resolution paths.

    This type is intentionally absent from package exports. It is not a public
    replacement for ModelClientConfiguration or InteractionOptions.
    """

    target: ModelTarget | None = None
    """Optional model target supplied by this configuration layer."""

    service_access: ServiceAccess | None = None
    """Optional service access value supplied by this layer."""

    compatibility_policy: CompatibilityPolicy | None = None
    """Optional compatibility policy supplied by this layer."""

    resource_limits: InteractionResourceLimits | None = None
    """Optional per-field resource-limit overrides supplied by this layer."""

    cancellation_signal: CancellationSignal | None = None
    """Optional interaction-owned cancellation signal reference."""

    def __post_init__(self) -> None:
        """Require each present field to satisfy its nominal storage contract."""
        target = cast(object, self.target)
        service_access = cast(object, self.service_access)
        compatibility_policy = cast(object, self.compatibility_policy)
        resource_limits = cast(object, self.resource_limits)
        cancellation_signal = cast(object, self.cancellation_signal)

        # Structural domain protocols remain open to custom implementations,
        # while None keeps the distinction between absence and an explicit value.
        if target is not None and not isinstance(target, ModelTarget):
            raise TypeError(
                "InteractionConfigurationLayer target must implement "
                "ModelTarget or be None."
            )
        if service_access is not None and not isinstance(
            service_access,
            ServiceAccess,
        ):
            raise TypeError(
                "InteractionConfigurationLayer service_access must implement "
                "ServiceAccess or be None."
            )

        # Concrete immutable values use nominal checks so arbitrary field-shaped
        # objects cannot enter the later configuration merger.
        if compatibility_policy is not None and not isinstance(
            compatibility_policy,
            CompatibilityPolicy,
        ):
            raise TypeError(
                "InteractionConfigurationLayer compatibility_policy must be "
                "CompatibilityPolicy or None."
            )
        if resource_limits is not None and not isinstance(
            resource_limits,
            InteractionResourceLimits,
        ):
            raise TypeError(
                "InteractionConfigurationLayer resource_limits must be "
                "InteractionResourceLimits or None."
            )

        # A signal is stored by reference and remains controlled by its producer;
        # this layer neither subscribes nor requests cancellation during creation.
        if cancellation_signal is not None and not isinstance(
            cancellation_signal,
            CancellationSignal,
        ):
            raise TypeError(
                "InteractionConfigurationLayer cancellation_signal must implement "
                "CancellationSignal or be None."
            )
