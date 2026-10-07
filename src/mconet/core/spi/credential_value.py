"""Open contract for controlled, non-serializable credential values."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import AuthorizedSecretConsumer, OpenIdentifier


@runtime_checkable
class CredentialValue(Protocol):
    """Expose credential shape and plaintext only through an authorized consumer.

    Concrete implementations may carry a string, bytes, a signing key, a token
    bundle, or another provider-specific runtime value. They must retain sensitive
    state in :class:`~mconet.core.domain.SecretValue` or an equivalent controlled
    container, redact every ordinary text representation, and reject ordinary
    serialization, copying, snapshots, and diagnostic extraction.

    This open structural contract has no registry identity or closed kind list.
    It deliberately exposes no public plaintext field, generic mapping, or
    persistence representation.
    """

    @property
    def kind(self) -> OpenIdentifier:
        """Return the non-sensitive open discriminator for this credential shape."""
        # Selection may observe the kind, but it must never infer, reveal, log,
        # serialize, or transform the credential's protected runtime value.
        ...

    def reveal(self, consumer: AuthorizedSecretConsumer) -> object:
        """Return protected runtime data only to a nominally authorized consumer."""
        # Implementations validate nominal authorization before reading secret
        # storage. The object result remains opaque to Core and non-handler code.
        ...
