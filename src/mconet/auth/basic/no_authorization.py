"""Explicit authorization decision that carries no credential."""

from __future__ import annotations

from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier

# The kind is the handler-selection key. It is not a credential and it is not a
# stand-in for an omitted authorization field.
NO_AUTHORIZATION_KIND = OpenIdentifier("authorization.none")
"""Stable discriminator for an explicit no-authorization decision."""

validate_open_identifier(NO_AUTHORIZATION_KIND)


class NoAuthorization:
    """State that an interaction is intentionally unauthenticated.

    The value implements Authorization and stores no credential, header, token,
    or signing material. Supplying this object is a completed decision. Leaving
    authorization unset is a different state and remains incomplete configuration.
    """

    __slots__ = ()

    @property
    def kind(self) -> OpenIdentifier:
        """Return the stable no-authorization discriminator."""
        # Every instance reports the same kind so handler matching does not
        # depend on which instance a configuration layer retained.
        return NO_AUTHORIZATION_KIND

    def __eq__(self, other: object) -> bool:
        """Return whether the other value is the same no-authorization decision."""
        # Exact type equality rejects a subclass that could add credential state
        # while still claiming to be this decision.
        return type(other) is NoAuthorization

    def __hash__(self) -> int:
        """Return a hash shared by every no-authorization instance."""
        # The hash matches equality: instances have no per-object state.
        return hash((NoAuthorization, NO_AUTHORIZATION_KIND))

    def __setattr__(self, name: str, value: object) -> None:
        """Reject attributes that could carry credential or header material."""
        del name, value
        raise AttributeError("NoAuthorization does not accept attributes.")

    def __delattr__(self, name: str) -> None:
        """Reject removal of the fixed decision surface."""
        del name
        raise AttributeError("NoAuthorization does not accept attributes.")

    def __repr__(self) -> str:
        """Return the decision name without any configuration payload."""
        return "NoAuthorization()"
