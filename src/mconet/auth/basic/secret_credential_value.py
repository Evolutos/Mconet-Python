"""Credential wrapper that reveals one secret value to an authorized consumer."""

from __future__ import annotations

from typing import Never, SupportsIndex

from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.secret_value import AuthorizedSecretConsumer, SecretValue
from mconet.core.spi.credential_value import CredentialValue

_REDACTED_TEXT = "[REDACTED]"
_CREDENTIAL_KIND = OpenIdentifier("credential.secret")
_SERIALIZATION_MESSAGE = "CredentialValue cannot be serialized."


class _SecretCredentialValue:
    """Expose one secret only through the authorized reveal path."""

    __slots__ = ("_kind", "_secret")

    _kind: OpenIdentifier
    _secret: SecretValue

    def __init__(self, secret: SecretValue) -> None:
        """Retain a secret container without reading it."""
        # The wrapper does not copy plaintext into its own storage. Reveal
        # remains delegated to SecretValue's consumer check.
        object.__setattr__(self, "_kind", _CREDENTIAL_KIND)
        object.__setattr__(self, "_secret", secret)

    @property
    def kind(self) -> OpenIdentifier:
        """Return the non-sensitive shape of a secret credential."""
        # The kind identifies a secret container. It is not the authorization
        # scheme and it does not disclose the protected value.
        return self._kind

    def reveal(self, consumer: AuthorizedSecretConsumer) -> object:
        """Return the secret only to an authorized consumer."""
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
        raise TypeError(_SERIALIZATION_MESSAGE)

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy reconstruction of the credential."""
        del protocol
        raise TypeError(_SERIALIZATION_MESSAGE)


def secret_credential_value(secret: SecretValue) -> CredentialValue:
    """Wrap one secret container as a credential value.

    Args:
        secret: Protected value already stored by a credential source.

    Returns:
        A credential that reveals ``secret`` only to an authorized consumer.
    """
    # Callers pass a SecretValue they already validated. This function does not
    # read or copy the plaintext before returning the wrapper.
    return _SecretCredentialValue(secret)
