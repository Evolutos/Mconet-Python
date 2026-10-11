"""Bearer authorization whose token comes only from a credential source."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.spi.credential_source import CredentialSource

# Handler selection uses this kind. The token is never part of the decision.
BEARER_AUTHORIZATION_KIND = OpenIdentifier("authorization.bearer")
"""Stable discriminator for bearer token authorization."""

validate_open_identifier(BEARER_AUTHORIZATION_KIND)
_IMMUTABLE_MESSAGE = "BearerAuthorization does not accept attributes."


class BearerAuthorization:
    """Identify a bearer decision without storing the token.

    The only configuration is the credential source that will supply the token
    when a handler applies the decision. There is no token field, header value,
    or prefix on this object. Construction does not call the source.
    """

    __slots__ = ("_credential_source", "_kind")

    _credential_source: CredentialSource
    _kind: OpenIdentifier

    def __init__(
        self,
        credential_source: CredentialSource,
        kind: OpenIdentifier = BEARER_AUTHORIZATION_KIND,
    ) -> None:
        """Retain one credential source for a later bearer handler.

        Args:
            credential_source: Source consulted only when a handler applies this
                decision.
            kind: Handler-selection discriminator. Only the bearer kind is
                accepted.

        Raises:
            TypeError: If a field does not have its required nominal type.
            ValueError: If ``kind`` is not ``authorization.bearer``.
        """
        source_value = cast(object, credential_source)
        kind_value = cast(object, kind)

        # The source is retained by identity. Construction must not resolve it,
        # so the token is not read while the decision is being stored.
        if not isinstance(source_value, CredentialSource):
            raise TypeError(
                "BearerAuthorization credential_source must implement CredentialSource."
            )

        # A substituted kind would select another handler for a decision that
        # has no token of its own to reinterpret.
        if not isinstance(kind_value, OpenIdentifier):
            raise TypeError("BearerAuthorization kind must be an OpenIdentifier.")
        if kind_value != BEARER_AUTHORIZATION_KIND:
            raise ValueError("BearerAuthorization kind must be authorization.bearer.")

        object.__setattr__(self, "_credential_source", source_value)
        object.__setattr__(self, "_kind", kind_value)

    @property
    def credential_source(self) -> CredentialSource:
        """Return the credential source without resolving it."""
        # Reading the reference does not call the source. The bearer handler
        # resolves it later, once per interaction.
        return self._credential_source

    @property
    def kind(self) -> OpenIdentifier:
        """Return the stable bearer discriminator."""
        return self._kind

    def __setattr__(self, name: str, value: object) -> None:
        """Reject a token attribute or replacement of the source."""
        del name, value
        raise AttributeError(_IMMUTABLE_MESSAGE)

    def __delattr__(self, name: str) -> None:
        """Reject removal of the fixed decision fields."""
        del name
        raise AttributeError(_IMMUTABLE_MESSAGE)

    def __eq__(self, other: object) -> bool:
        """Return whether the other value uses the same bearer source."""
        if type(other) is not BearerAuthorization:
            return False
        return (
            self._credential_source == other._credential_source
            and self._kind == other._kind
        )

    def __hash__(self) -> int:
        """Return a hash of the bearer source and kind."""
        # Different sources must not collapse to one hash. The token is not an
        # input to this hash because this decision does not store one.
        return hash((self._credential_source, self._kind))

    def __repr__(self) -> str:
        """Return the decision without rendering the credential source."""
        # The source may render a token. Its presence is named, but its text is
        # omitted from this decision's own representation.
        return (
            "BearerAuthorization("
            "credential_source=<CredentialSource>, "
            f"kind={self._kind!r})"
        )
