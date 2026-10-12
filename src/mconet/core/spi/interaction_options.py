"""Immutable per-interaction overrides that are not written back to a client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.domain.compatibility_policy import CompatibilityPolicy
from mconet.core.domain.interaction_resource_limits import InteractionResourceLimits
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.spi.monitoring_options import MonitoringOptions
from mconet.core.spi.runtime_components import RuntimeComponents


@dataclass(frozen=True, slots=True)
class InteractionOptions:
    """Store one interaction's overrides, cancellation, and monitoring choices.

    ``None`` means this interaction does not override that client or request
    value. ``components`` replaces only the roles it sets and is not copied
    back onto the client. ``monitoring_options`` is separate from components.
    ``include_raw_response`` records whether a later stage may retain a raw
    response; this value does not capture one.

    Cancellation belongs only to this interaction. R1 does not include request
    normalizers. Construction checks nominal types and does not subscribe to
    cancellation, merge monitors, or validate injected component protocols.
    """

    components: RuntimeComponents | None = None
    """Optional interaction-level direct component injection."""

    service_access_override: ServiceAccess | None = None
    """Optional access layer above the request and client defaults."""

    compatibility_policy: CompatibilityPolicy | None = None
    """Optional interaction compatibility policy above the client default."""

    resource_limits: InteractionResourceLimits | None = None
    """Optional interaction byte limits above the client default."""

    monitoring_options: MonitoringOptions | None = None
    """Optional interaction monitoring options, separate from components."""

    cancellation_signal: CancellationSignal | None = None
    """Optional caller-owned cancellation signal for this interaction only."""

    include_raw_response: bool = False
    """Whether a later stage may retain one raw response snapshot."""

    def __post_init__(self) -> None:
        """Require each supplied override to use its nominal type."""
        components = cast(object, self.components)
        service_access_override = cast(object, self.service_access_override)
        compatibility_policy = cast(object, self.compatibility_policy)
        resource_limits = cast(object, self.resource_limits)
        monitoring_options = cast(object, self.monitoring_options)
        cancellation_signal = cast(object, self.cancellation_signal)
        include_raw_response = cast(object, self.include_raw_response)

        # None is an absent override. A present value is stored unchanged so a
        # later interaction cannot mutate the client's configuration through it.
        if components is not None and not isinstance(components, RuntimeComponents):
            raise TypeError("components must be a RuntimeComponents or None.")
        if service_access_override is not None and not isinstance(
            service_access_override, ServiceAccess
        ):
            raise TypeError("service_access_override must be a ServiceAccess or None.")
        if compatibility_policy is not None and not isinstance(
            compatibility_policy, CompatibilityPolicy
        ):
            raise TypeError(
                "compatibility_policy must be a CompatibilityPolicy or None."
            )
        if resource_limits is not None and not isinstance(
            resource_limits, InteractionResourceLimits
        ):
            raise TypeError(
                "resource_limits must be an InteractionResourceLimits or None."
            )
        if monitoring_options is not None and not isinstance(
            monitoring_options, MonitoringOptions
        ):
            raise TypeError("monitoring_options must be a MonitoringOptions or None.")
        if cancellation_signal is not None and not isinstance(
            cancellation_signal, CancellationSignal
        ):
            raise TypeError("cancellation_signal must be a CancellationSignal or None.")
        if type(include_raw_response) is not bool:
            raise TypeError("include_raw_response must be a bool.")
