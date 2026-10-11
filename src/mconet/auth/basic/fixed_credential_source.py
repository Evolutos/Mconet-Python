"""Credential source that retains one fixed secret value."""

from __future__ import annotations

from typing import Never, SupportsIndex, cast

from mconet.auth.basic.secret_credential_value import secret_credential_value
from mconet.core.domain.secret_value import SecretValue
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.credential_value import CredentialValue

_REDACTED_TEXT = "[REDACTED]"
_SERIALIZATION_MESSAGE = "FixedCredentialSource cannot be serialized."


class FixedCredentialSource:
    """Resolve the same SecretValue for every authorization interaction.

    The secret is stored only as a :class:`SecretValue`. Resolution does not
    call a provider, refresh the secret, or copy its plaintext into another
    field. Each call returns a new credential wrapper around that same secret.
    """

    __slots__ = ("_secret",)

    _secret: SecretValue

    def __init__(self, secret: SecretValue) -> None:
        """Retain one secret container.

        Args:
            secret: Protected value returned by later resolutions.

        Raises:
            TypeError: If ``secret`` is not a SecretValue. A plain string is
                rejected so the key is not stored as an ordinary attribute.
        """
        candidate = cast(object, secret)
        # A raw string would become an ordinary field and could appear in
        # repr, logs, or serialization. Only the controlled container is stored.
        if not isinstance(candidate, SecretValue):
            raise TypeError("FixedCredentialSource secret must be a SecretValue.")
        object.__setattr__(self, "_secret", candidate)

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Return the fixed secret for one interaction without reading it.

        Args:
            context: Non-sensitive authorization facts for this interaction.

        Returns:
            A credential whose reveal path exposes the stored secret.

        Raises:
            TypeError: If ``context`` is not an AuthorizationContext.
        """
        candidate = cast(object, context)
        # The context is required by the source contract and contains no
        # credential. A fixed secret does not vary with its fields.
        if not isinstance(candidate, AuthorizationContext):
            raise TypeError(
                "FixedCredentialSource context must be an AuthorizationContext."
            )
        return secret_credential_value(self._secret)

    def __setattr__(self, name: str, value: object) -> None:
        """Reject replacement of the stored secret."""
        del name, value
        raise AttributeError("FixedCredentialSource does not accept attributes.")

    def __str__(self) -> str:
        """Return a fixed redaction marker instead of the stored secret."""
        return _REDACTED_TEXT

    def __repr__(self) -> str:
        """Return the same redaction marker used by containers and logs."""
        return _REDACTED_TEXT

    def __format__(self, format_spec: str) -> str:
        """Apply formatting only to the redaction marker."""
        return format(_REDACTED_TEXT, format_spec)

    def __getstate__(self) -> Never:
        """Reject state serialization before the secret slot is inspected."""
        raise TypeError(_SERIALIZATION_MESSAGE)

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy reconstruction of the fixed source."""
        del protocol
        raise TypeError(_SERIALIZATION_MESSAGE)
