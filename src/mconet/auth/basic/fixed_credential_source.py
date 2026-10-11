"""Credential source that retains one fixed secret value."""

from __future__ import annotations

from typing import Never, SupportsIndex, cast

from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.secret_value import AuthorizedSecretConsumer, SecretValue
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.credential_value import CredentialValue

_REDACTED_TEXT = "[REDACTED]"
_CREDENTIAL_KIND = OpenIdentifier("credential.secret")
_SERIALIZATION_MESSAGE = "FixedCredentialSource cannot be serialized."
_CREDENTIAL_SERIALIZATION_MESSAGE = "CredentialValue cannot be serialized."


class _FixedCredentialValue:
    """Expose one fixed secret only through the authorized reveal path."""

    __slots__ = ("_kind", "_secret")

    _kind: OpenIdentifier
    _secret: SecretValue

    def __init__(self, secret: SecretValue) -> None:
        """Retain the source's secret container without reading it."""
        # The wrapper does not copy plaintext into its own storage. Reveal
        # remains delegated to SecretValue's consumer check.
        object.__setattr__(self, "_kind", _CREDENTIAL_KIND)
        object.__setattr__(self, "_secret", secret)

    @property
    def kind(self) -> OpenIdentifier:
        """Return the non-sensitive shape of a fixed secret credential."""
        # The kind identifies a secret container. It is not the authorization
        # scheme and it does not disclose the protected value.
        return self._kind

    def reveal(self, consumer: AuthorizedSecretConsumer) -> object:
        """Return the fixed secret only to an authorized consumer."""
        # SecretValue performs the nominal handler check. This wrapper cannot
        # bypass it or cache the revealed plaintext.
        return self._secret.reveal(consumer)

    def __setattr__(self, name: str, value: object) -> None:
        """Reject replacement of the protected secret."""
        del name, value
        raise AttributeError("CredentialValue does not accept attributes.")

    def __str__(self) -> str:
        """Return a fixed redaction marker instead of the secret."""
        return _REDACTED_TEXT

    def __repr__(self) -> str:
        """Return the same redaction marker used by containers and logs."""
        return _REDACTED_TEXT

    def __format__(self, format_spec: str) -> str:
        """Apply formatting only to the redaction marker."""
        return format(_REDACTED_TEXT, format_spec)

    def __getstate__(self) -> Never:
        """Reject state serialization before the secret slot is inspected."""
        raise TypeError(_CREDENTIAL_SERIALIZATION_MESSAGE)

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy reconstruction of the credential."""
        del protocol
        raise TypeError(_CREDENTIAL_SERIALIZATION_MESSAGE)


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
        return _FixedCredentialValue(self._secret)

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
