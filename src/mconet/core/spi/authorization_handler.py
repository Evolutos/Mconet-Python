"""Contract for applying opaque authorization to an encoded request."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import Authorization
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.body_signing_requirement import (
    BodySigningMode,
    BodySigningRequirement,
)
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class AuthorizationHandler(RuntimeComponent, Protocol):
    """Match and apply one opaque authorization mechanism.

    :meth:`supports` reports every signing mode that the handler can apply for
    the supplied authorization and protocol requirement. It is synchronous and
    side-effect-free: capability matching must not reveal credentials, mutate a
    request, acquire dynamic credentials, or perform I/O.

    :meth:`apply` runs only after resolution selected this exact handler and one
    compatible mode in :class:`AuthorizationContext`. It may acquire and consume
    credentials and replace URL, headers, query parameters, or encoded body only
    through the supplied open :class:`MutableTransportRequest`. It must not send
    or freeze the request, perform transport I/O, or choose another signing mode.

    Concrete handlers that reveal protected values additionally subclass the
    nominal ``AuthorizedSecretConsumer`` marker. Structural protocol conformance
    alone never grants access to :class:`SecretValue` or :class:`CredentialValue`.
    """

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return immutable compatible modes without authorization side effects."""
        # Resolution intersects this complete mode set with protocol preference;
        # an empty set means the candidate cannot handle the supplied facts.
        ...

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Apply authorization inside the open request-mutation window."""
        # The awaitable boundary permits dynamic credential acquisition while
        # request replacement remains bounded by MutableTransportRequest.
        ...
