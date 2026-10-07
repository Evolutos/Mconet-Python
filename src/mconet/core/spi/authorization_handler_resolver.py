"""Contract for deterministic authorization handler resolution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import Authorization
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.body_signing_requirement import BodySigningRequirement
from mconet.core.spi.resolved_authorization_handler import (
    ResolvedAuthorizationHandler,
)
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class AuthorizationHandlerResolver(RuntimeComponent, Protocol):
    """Select exactly one authorization component and body-signing mode.

    Implementations evaluate the opaque authorization value and signing
    requirement against the complete immutable candidate tuple. A successful
    resolution returns the single compatible component and mode without using
    candidate order as a tie-breaker.

    Resolution is synchronous and side-effect-free. It must not reveal
    credentials, mutate or authorize a transport request, perform network I/O,
    or consult candidates outside the supplied interaction snapshot. No
    compatible authorization component, no compatible signing mode, and more
    than one compatible component are deterministic pre-interaction failures.

    Every candidate implements :class:`AuthorizationHandler`, so resolution may
    query compatibility without accepting unrelated runtime components.
    """

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Return the unique compatible handler and signing-mode selection."""
        # Implementations inspect all supplied candidates as one closed set so
        # zero and multiple matches fail instead of selecting by tuple order.
        ...
