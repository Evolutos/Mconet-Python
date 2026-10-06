"""Controlled in-memory values for authorization secrets."""

from __future__ import annotations

from typing import Never, Self, SupportsIndex, cast

from mconet.core.domain.bytes_value import Bytes


class AuthorizedSecretConsumer:
    """Nominal marker for components permitted to consume secret plaintext.

    Concrete authorization handlers subclass this marker. The marker itself is
    not directly constructible, preventing an untyped object from accidentally
    satisfying the access boundary through structural matching.
    """

    __slots__ = ()

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        """Create only concrete consumer subclasses."""
        del args, kwargs
        if cls is AuthorizedSecretConsumer:
            raise TypeError(
                "AuthorizedSecretConsumer must be implemented by a concrete "
                "authorization handler."
            )
        return super().__new__(cls)


class SecretValue:
    """Store string or byte secrets behind an explicit consumer boundary.

    The object exposes no plaintext property and has no instance dictionary.
    ``reveal`` is the only supported read path. Ordinary object serialization is
    rejected; persistence and credential refresh remain application concerns.
    """

    __slots__ = ("__value",)

    def __init__(self, value: str | Bytes) -> None:
        """Store one immutable string or domain Bytes secret."""
        candidate = cast(object, value)
        # Bytes is a zero-cost NewType over bytes and therefore has no distinct
        # runtime class. Static typing enforces the nominal public boundary.
        if not isinstance(candidate, (str, bytes)):
            raise TypeError("SecretValue must contain a string or Bytes value.")
        object.__setattr__(self, "_SecretValue__value", candidate)

    def __setattr__(self, name: str, value: object) -> None:
        """Reject mutation after construction."""
        del name, value
        raise AttributeError("SecretValue is immutable.")

    def reveal(self, consumer: AuthorizedSecretConsumer) -> str | Bytes:
        """Return plaintext only to a nominally authorized consumer.

        Args:
            consumer: A concrete authorization component that owns plaintext use.

        Returns:
            The stored string or immutable byte value.

        Raises:
            TypeError: If the caller is not an authorized secret consumer.
        """
        candidate = cast(object, consumer)
        if not isinstance(candidate, AuthorizedSecretConsumer):
            raise TypeError("SecretValue consumer is not authorized.")
        return self.__value

    def __getstate__(self) -> Never:
        """Reject state-based serializers before plaintext can be extracted."""
        raise TypeError("SecretValue cannot be serialized.")

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Reject pickle and copy protocols that request a reconstruction state."""
        del protocol
        raise TypeError("SecretValue cannot be serialized.")
