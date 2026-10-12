"""Immutable client defaults and direct component injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.interaction_resource_limits import InteractionResourceLimits
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.spi.monitoring_options import MonitoringOptions
from mconet.core.spi.runtime_components import RuntimeComponents


@dataclass(frozen=True, slots=True)
class ModelClientConfiguration:
    """Store one reusable client's defaults and injected components.

    Every field is optional. ``None`` means this client does not supply that
    default; a later resolution step applies the request, interaction, or SDK
    value. ``components`` is the client layer of direct injection.
    ``monitoring_defaults`` is separate from components because monitors are not
    runtime component roles.

    R1 does not include request normalizers. This value does not merge layers,
    resolve access, read credentials, or run component SPI, type-contract, or
    lifecycle validation. Those checks belong to client construction.
    """

    default_target: ModelTarget | None = None
    """Optional client default target used when a request does not select one."""

    default_service_access: ServiceAccess | None = None
    """Optional client default access below the request and interaction layers."""

    default_compatibility_policy: CompatibilityPolicy | None = None
    """Optional client compatibility policy below an interaction override."""

    default_resource_limits: InteractionResourceLimits | None = None
    """Optional client byte limits below an interaction override."""

    components: RuntimeComponents | None = None
    """Optional client-level direct component injection."""

    monitoring_defaults: MonitoringOptions | None = None
    """Optional client monitoring options, separate from injected components."""

    def __post_init__(self) -> None:
        """Require each supplied field to use its nominal configuration type."""
        default_target = cast(object, self.default_target)
        default_service_access = cast(object, self.default_service_access)
        default_compatibility_policy = cast(object, self.default_compatibility_policy)
        default_resource_limits = cast(object, self.default_resource_limits)
        components = cast(object, self.components)
        monitoring_defaults = cast(object, self.monitoring_defaults)

        # None remains the explicit absence of a client default. A present value
        # must already be the domain or SPI type; this object does not repair it.
        if default_target is not None and not isinstance(default_target, ModelTarget):
            raise TypeError("default_target must be a ModelTarget or None.")
        if default_service_access is not None and not isinstance(
            default_service_access, ServiceAccess
        ):
            raise TypeError("default_service_access must be a ServiceAccess or None.")
        if default_compatibility_policy is not None and not isinstance(
            default_compatibility_policy, CompatibilityPolicy
        ):
            raise TypeError(
                "default_compatibility_policy must be a CompatibilityPolicy or None."
            )
        if default_resource_limits is not None and not isinstance(
            default_resource_limits, InteractionResourceLimits
        ):
            raise TypeError(
                "default_resource_limits must be an InteractionResourceLimits or None."
            )
        if components is not None and not isinstance(components, RuntimeComponents):
            raise TypeError("components must be a RuntimeComponents or None.")
        if monitoring_defaults is not None and not isinstance(
            monitoring_defaults, MonitoringOptions
        ):
            raise TypeError("monitoring_defaults must be a MonitoringOptions or None.")
