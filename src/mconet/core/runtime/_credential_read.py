"""Runtime scheduling for one interaction credential read."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.credential_source import CredentialSource
from mconet.core.spi.credential_value import CredentialValue


async def read_interaction_credential(
    authorization: Authorization,
    context: AuthorizationContext,
) -> CredentialValue | None:
    """Read one credential when the decision exposes a credential source.

    A decision with no source returns ``None`` and does not invent a
    credential. A source is called once. Its failure propagates unchanged and
    is not retried, so a later stage must not apply a handler or send the
    request. This function does not call ``apply`` or transport.

    Args:
        authorization: Opaque decision that may own a credential source.
        context: Non-sensitive facts passed to that source.

    Returns:
        The credential from the one source call, or ``None`` when the decision
        has no source.

    Raises:
        TypeError: If an argument or the source result has an invalid type.
        BaseException: The source's exact failure.
    """
    authorization_value = cast(object, authorization)
    context_value = cast(object, context)
    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")
    if not isinstance(context_value, AuthorizationContext):
        raise TypeError("context must be an AuthorizationContext.")

    source = cast(object, getattr(authorization_value, "credential_source", None))
    # NoAuthorization and other decisions without a source are valid. They do
    # not become an empty credential.
    if source is None:
        return None
    if not isinstance(source, CredentialSource):
        raise TypeError("credential_source must implement CredentialSource.")
    credential = cast(object, await source.resolve(context_value))
    # A source that returns an ordinary string would let plaintext cross this
    # boundary. Only a credential value may continue.
    if not isinstance(credential, CredentialValue):
        raise TypeError("credential source must return a CredentialValue.")
    return credential
