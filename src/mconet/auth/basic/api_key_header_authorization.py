"""API key authorization that keeps the header, prefix, and source separate."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.spi.credential_source import CredentialSource

# Handler selection uses this kind. The header name and prefix are configuration,
# and the credential itself stays behind the separate source.
API_KEY_HEADER_AUTHORIZATION_KIND = OpenIdentifier("authorization.api_key_header")
"""Stable discriminator for header API key authorization."""

validate_open_identifier(API_KEY_HEADER_AUTHORIZATION_KIND)
_IMMUTABLE_MESSAGE = "ApiKeyHeaderAuthorization does not accept attributes."


class ApiKeyHeaderAuthorization:
    """Name one header and prefix whose value comes from a credential source.

    The header name, prefix, and credential source are independent fields. This
    value does not store the key, concatenate a header, or call the source.
    HTTP token and control-character checks belong to the authorization header
    validators, so the supplied name and prefix are stored unchanged.
    """

    __slots__ = ("_credential_source", "_header_name", "_kind", "_prefix")

    _header_name: str
    _prefix: str
    _credential_source: CredentialSource
    _kind: OpenIdentifier

    def __init__(
        self,
        header_name: str,
        prefix: str,
        credential_source: CredentialSource,
        kind: OpenIdentifier = API_KEY_HEADER_AUTHORIZATION_KIND,
    ) -> None:
        """Store separated header configuration and one credential source.

        Args:
            header_name: Exact header name that will receive the key.
            prefix: Exact text placed before the key. An empty string is kept.
            credential_source: Source consulted only when a handler applies this
                decision.
            kind: Handler-selection discriminator. Only the API key header kind
                is accepted.

        Raises:
            TypeError: If a field does not have its required nominal type.
            ValueError: If ``kind`` is not ``authorization.api_key_header``.
        """
        header_name_value = cast(object, header_name)
        prefix_value = cast(object, prefix)
        source_value = cast(object, credential_source)
        kind_value = cast(object, kind)

        # Store the caller's text without trimming or folding. Empty text remains
        # explicit so a later validator can reject it instead of guessing a name.
        if not isinstance(header_name_value, str):
            raise TypeError("ApiKeyHeaderAuthorization header_name must be a string.")
        if not isinstance(prefix_value, str):
            raise TypeError("ApiKeyHeaderAuthorization prefix must be a string.")

        # The source is retained by identity. Construction must not resolve it,
        # so no credential is read while the decision is being stored.
        if not isinstance(source_value, CredentialSource):
            raise TypeError(
                "ApiKeyHeaderAuthorization credential_source must implement "
                "CredentialSource."
            )

        # A substituted kind would make this object match a different handler
        # while still exposing API-key fields.
        if not isinstance(kind_value, OpenIdentifier):
            raise TypeError("ApiKeyHeaderAuthorization kind must be an OpenIdentifier.")
        if kind_value != API_KEY_HEADER_AUTHORIZATION_KIND:
            raise ValueError(
                "ApiKeyHeaderAuthorization kind must be authorization.api_key_header."
            )

        # Slots are private so assignment goes through the rejecting setattr
        # after initialization. object.__setattr__ is the one construction path.
        object.__setattr__(self, "_header_name", header_name_value)
        object.__setattr__(self, "_prefix", prefix_value)
        object.__setattr__(self, "_credential_source", source_value)
        object.__setattr__(self, "_kind", kind_value)

    @property
    def header_name(self) -> str:
        """Return the exact header name that will receive the key."""
        return self._header_name

    @property
    def prefix(self) -> str:
        """Return the exact prefix placed before the key."""
        return self._prefix

    @property
    def credential_source(self) -> CredentialSource:
        """Return the credential source without resolving it."""
        # Reading the reference does not call the source. Handlers resolve it
        # later, once per interaction.
        return self._credential_source

    @property
    def kind(self) -> OpenIdentifier:
        """Return the stable API key header discriminator."""
        return self._kind

    def __setattr__(self, name: str, value: object) -> None:
        """Reject replacement of configuration and any added key material."""
        del name, value
        raise AttributeError(_IMMUTABLE_MESSAGE)

    def __delattr__(self, name: str) -> None:
        """Reject removal of the fixed decision fields."""
        del name
        raise AttributeError(_IMMUTABLE_MESSAGE)

    def __eq__(self, other: object) -> bool:
        """Return whether the other value has the same separated configuration."""
        if type(other) is not ApiKeyHeaderAuthorization:
            return False
        # Source equality is the source's own contract. Identity remains the
        # usual result for a source that does not define value equality.
        return (
            self._header_name == other._header_name
            and self._prefix == other._prefix
            and self._credential_source == other._credential_source
            and self._kind == other._kind
        )

    def __hash__(self) -> int:
        """Return a hash of the separated configuration."""
        # Include the source so two decisions that read different sources do not
        # collapse to one hash merely because their header text matches.
        return hash(
            (
                self._header_name,
                self._prefix,
                self._credential_source,
                self._kind,
            )
        )

    def __repr__(self) -> str:
        """Return header configuration without the credential source rendering."""
        # The source may render protected material. Its presence is named, but
        # its text is omitted from this decision's own representation.
        return (
            "ApiKeyHeaderAuthorization("
            f"header_name={self._header_name!r}, "
            f"prefix={self._prefix!r}, "
            "credential_source=<CredentialSource>, "
            f"kind={self._kind!r})"
        )
