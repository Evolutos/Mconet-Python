"""Asynchronous contract for resolving interaction-local credential values."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.credential_value import CredentialValue


@runtime_checkable
class CredentialSource(Protocol):
    """Resolve one protected credential for each authorization interaction.

    Implementations may read a keychain, keystore, environment, vault, security
    token service, enterprise broker, or another application-owned provider. Each
    call receives immutable non-sensitive authorization facts and returns one
    controlled :class:`CredentialValue` for that interaction.

    The contract deliberately defines no SDK-owned cache, persistence, refresh,
    retry, logging, registry, or plaintext field. Implementations own provider
    policy while preserving cancellation and failure through the awaitable call.
    """

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Resolve one interaction-local credential from non-sensitive context."""
        # Runtime invokes the source for every authorization operation. A failure
        # terminates this call without yielding a partial or stale credential.
        ...
