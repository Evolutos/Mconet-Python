"""Credential source that asks a provider again for every interaction."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import iscoroutinefunction
from typing import Never, SupportsIndex, cast

from mconet.auth.basic.secret_credential_value import secret_credential_value
from mconet.core.domain.secret_value import SecretValue
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.credential_value import CredentialValue

_REDACTED_TEXT = "[REDACTED]"
_SERIALIZATION_MESSAGE = "DynamicCredentialSource cannot be serialized."
CredentialProvider = Callable[[AuthorizationContext], Awaitable[SecretValue]]


class DynamicCredentialSource:
    """Resolve a credential by calling a business provider for each interaction.

    The provider is not called during construction, and a successful result is
    not reused for a later interaction. The returned credential wraps the
    provider's SecretValue. This source does not refresh, retry, or cache.
    """

    __slots__ = ("_provider",)

    _provider: CredentialProvider

    def __init__(self, provider: CredentialProvider) -> None:
        """Retain one asynchronous provider.

        Args:
            provider: Callable invoked once per ``resolve``. It must return a
                SecretValue for that interaction.

        Raises:
            TypeError: If ``provider`` is not an asynchronous callable.
        """
        candidate = cast(object, provider)
        # A synchronous provider would block the authorization boundary and
        # could hide a stale value captured at construction.
        if not callable(candidate) or not _is_async_provider(candidate):
            raise TypeError("DynamicCredentialSource provider must be asynchronous.")
        object.__setattr__(self, "_provider", provider)

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Call the provider and wrap the secret it returns for this call.

        Args:
            context: Non-sensitive authorization facts passed to the provider.

        Returns:
            A credential wrapping the SecretValue returned by this invocation.

        Raises:
            TypeError: If ``context`` is not an AuthorizationContext, or if the
                provider returns a value that is not a SecretValue. The returned
                text is not included.
            BaseException: The provider's exact failure, without substitution.
        """
        candidate = cast(object, context)
        # Reject a bad context before the provider runs so business code does
        # not observe a value that failed the authorization contract.
        if not isinstance(candidate, AuthorizationContext):
            raise TypeError(
                "DynamicCredentialSource context must be an AuthorizationContext."
            )
        secret = await self._provider(candidate)
        secret_value = cast(object, secret)
        # Do not interpolate the returned object. A mistaken provider can return
        # the plaintext itself, and that text must not enter the error.
        if not isinstance(secret_value, SecretValue):
            raise TypeError(
                "DynamicCredentialSource provider must return a SecretValue."
            )
        return secret_credential_value(secret_value)

    def __setattr__(self, name: str, value: object) -> None:
        """Reject replacement of the provider."""
        del name, value
        raise AttributeError("DynamicCredentialSource does not accept attributes.")

    def __str__(self) -> str:
        """Return a fixed redaction marker instead of provider state."""
        return _REDACTED_TEXT

    def __repr__(self) -> str:
        """Return the same redaction marker used by containers and logs."""
        return _REDACTED_TEXT

    def __format__(self, format_spec: str) -> str:
        """Apply formatting only to the redaction marker."""
        return format(_REDACTED_TEXT, format_spec)

    def __getstate__(self) -> Never:
        """Reject state serialization of the provider and any closed-over state."""
        raise TypeError(_SERIALIZATION_MESSAGE)

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy reconstruction of the dynamic source."""
        del protocol
        raise TypeError(_SERIALIZATION_MESSAGE)


def _is_async_provider(provider: object) -> bool:
    """Return whether one callable awaits a provider result."""
    if not callable(provider):
        return False
    # Cover both functions and objects whose call implements the provider.
    call = cast(object, type(provider).__call__)
    return iscoroutinefunction(provider) or iscoroutinefunction(call)
