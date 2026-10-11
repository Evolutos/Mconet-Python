"""Authorization handler that adds one bearer token header."""

from __future__ import annotations

from typing import cast

from mconet.auth.basic.bearer_authorization import BearerAuthorization
from mconet.core.domain.authorization import Authorization
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.header_field import HeaderField
from mconet.core.domain.headers import Headers
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.secret_value import AuthorizedSecretConsumer
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.body_signing_requirement import (
    BodySigningMode,
    BodySigningRequirement,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.credential_value import CredentialValue
from mconet.core.spi.mutable_transport_request import MutableTransportRequest

_AUTHENTICATION_CATEGORY = ErrorCategory(OpenIdentifier("authentication"))
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_AUTHENTICATION_PHASE = InteractionPhase(OpenIdentifier("authentication"))
_UNSUPPORTED_AUTHORIZATION_CODE = "unsupported_authorization"
_UNSUPPORTED_AUTHORIZATION_MESSAGE = "Authorization is not a bearer decision."
_UNSUPPORTED_BODY_SIGNING_CODE = "unsupported_body_signing"
_UNSUPPORTED_BODY_SIGNING_MESSAGE = "Bearer authorization cannot sign a body."
_CREDENTIAL_TYPE_MESSAGE = "Bearer credential must be text."
_BEARER_HEADER_NAME = "Authorization"
_BEARER_PREFIX = "Bearer "
_HANDLER_NAME = "bearer-authorization-handler"
_HANDLER_VERSION = "1.0.0"

BEARER_AUTHORIZATION_HANDLER_DESCRIPTOR = ComponentDescriptor(
    _HANDLER_NAME,
    _HANDLER_VERSION,
    "builtin",
)
"""Diagnostic metadata for the bearer authorization handler."""


class BearerAuthorizationHandler(AuthorizedSecretConsumer):
    """Add an Authorization bearer header and leave the payload unchanged.

    The token comes from the decision's credential source. The handler supplies
    the ``Bearer`` scheme and does not replace the URL, query, body, or method.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared builtin diagnostic metadata."""
        return BEARER_AUTHORIZATION_HANDLER_DESCRIPTOR

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return ``none`` only for a bearer decision.

        Args:
            authorization: Opaque authorization value to match.
            body_signing_requirement: Protocol signing constraint.

        Returns:
            A one-element set containing ``none``, or an empty set when this
            handler cannot apply the supplied facts.

        Raises:
            TypeError: If ``body_signing_requirement`` has the wrong nominal type.
        """
        requirement = cast(object, body_signing_requirement)
        if not isinstance(requirement, BodySigningRequirement):
            raise TypeError(
                "body_signing_requirement must be a BodySigningRequirement."
            )
        # Match the decision type without resolving its credential source.
        if type(authorization) is not BearerAuthorization:
            return frozenset()
        if "none" not in requirement.acceptable_modes:
            return frozenset()
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Append the bearer header without changing the encoded payload.

        Args:
            authorization: Bearer decision selected for this interaction.
            context: Non-sensitive facts passed to the credential source.
            request: Open mutation window that receives the bearer header.

        Raises:
            TypeError: If ``context`` or ``request`` has the wrong nominal type,
                or if the revealed credential is not text.
            ModelInteractionError: If the decision does not belong to this
                handler, or if the selected signing mode is not ``none``.
            BaseException: The credential source's exact failure.
        """
        context_value = cast(object, context)
        request_value = cast(object, request)
        if not isinstance(context_value, AuthorizationContext):
            raise TypeError("context must be an AuthorizationContext.")
        if not isinstance(request_value, MutableTransportRequest):
            raise TypeError("request must be a MutableTransportRequest.")
        if type(authorization) is not BearerAuthorization:
            raise _unsupported_authorization_error()
        if context_value.body_signing_mode != "none":
            raise _unsupported_body_signing_error()

        credential = await authorization.credential_source.resolve(context_value)
        token = _token(self, credential)
        # Append the scheme header. Existing headers and the encoded body stay.
        request_value.replace_headers(
            Headers(
                (
                    *request_value.headers.values,
                    HeaderField(_BEARER_HEADER_NAME, f"{_BEARER_PREFIX}{token}"),
                )
            )
        )


def _token(consumer: AuthorizedSecretConsumer, credential: CredentialValue) -> str:
    """Reveal one bearer token without accepting a non-text credential."""
    revealed = credential.reveal(consumer)
    # A byte credential is not a bearer token. Omit it from the error so the
    # failure cannot become another copy of the token.
    if not isinstance(revealed, str):
        raise TypeError(_CREDENTIAL_TYPE_MESSAGE)
    return revealed


def _unsupported_authorization_error() -> ModelInteractionError:
    """Create the failure for a decision this handler does not own."""
    return ModelInteractionError(
        category=_AUTHENTICATION_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_UNSUPPORTED_AUTHORIZATION_CODE,
        message=_UNSUPPORTED_AUTHORIZATION_MESSAGE,
    )


def _unsupported_body_signing_error() -> ModelInteractionError:
    """Create the failure for a signing mode this handler cannot apply."""
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_UNSUPPORTED_BODY_SIGNING_CODE,
        message=_UNSUPPORTED_BODY_SIGNING_MESSAGE,
    )
