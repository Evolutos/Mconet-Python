"""Contract for side-effect-free service access configuration resolution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import ResolvedServiceAccess, ServiceAccess
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class ServiceAccessResolver(RuntimeComponent, Protocol):
    """Resolve four ordered access sources into one complete immutable snapshot.

    Implementations merge each access field from highest to lowest priority:
    interaction override, request access, client default, then protocol default.
    Authorization remains one opaque atomic value rather than a collection of
    independently merged credential properties.

    Resolution is synchronous and side-effect-free. It must not read credentials,
    call a credential source, perform network I/O, mutate any source, authorize a
    request, or use a component registry.
    """

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Resolve ordered access layers into one complete immutable value."""
        # Implementations observe all four original layers so every field can
        # independently select its first explicit value without external effects.
        ...
