"""Authorization handler that leaves a request unchanged."""

from __future__ import annotations

from typing import cast

from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.core.domain.authorization import Authorization
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.body_signing_requirement import (
    BodySigningMode,
    BodySigningRequirement,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.mutable_transport_request import MutableTransportRequest

_AUTHENTICATION_CATEGORY = ErrorCategory(OpenIdentifier("authentication"))
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_AUTHENTICATION_PHASE = InteractionPhase(OpenIdentifier("authentication"))
_UNSUPPORTED_AUTHORIZATION_CODE = "unsupported_authorization"
_UNSUPPORTED_AUTHORIZATION_MESSAGE = (
    "Authorization is not the explicit no-authorization decision."
)
_UNSUPPORTED_BODY_SIGNING_CODE = "unsupported_body_signing"
_UNSUPPORTED_BODY_SIGNING_MESSAGE = "No-authorization cannot apply a body-signing mode."
_HANDLER_NAME = "no-authorization-handler"
_HANDLER_VERSION = "1.0.0"

NO_AUTHORIZATION_HANDLER_DESCRIPTOR = ComponentDescriptor(
    _HANDLER_NAME,
    _HANDLER_VERSION,
    "builtin",
)
"""Diagnostic metadata for the no-authorization handler."""


class NoAuthorizationHandler:
    """Accept only an explicit no-authorization decision and do not sign.

    ``supports`` returns ``none`` only for :class:`NoAuthorization` when the
    protocol accepts that mode. ``apply`` does not read a credential, replace
    the request, or freeze it.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared builtin diagnostic metadata."""
        return NO_AUTHORIZATION_HANDLER_DESCRIPTOR

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return ``none`` only for an explicit no-authorization decision.

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
        # Matching uses the decision type only. Other authorization objects may
        # hold credential sources, and this handler does not read them.
        if type(authorization) is not NoAuthorization:
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
        """Leave the open request unchanged when no authorization is required.

        Args:
            authorization: Decision selected for this interaction.
            context: Non-sensitive facts, including the selected signing mode.
            request: Open mutation window. This method does not write to it.

        Raises:
            TypeError: If ``context`` or ``request`` has the wrong nominal type.
            ModelInteractionError: If the decision is not no-authorization, or
                if the selected signing mode is not ``none``.
        """
        context_value = cast(object, context)
        request_value = cast(object, request)
        if not isinstance(context_value, AuthorizationContext):
            raise TypeError("context must be an AuthorizationContext.")
        if not isinstance(request_value, MutableTransportRequest):
            raise TypeError("request must be a MutableTransportRequest.")
        # A different decision is not applied and its credential source is not
        # consulted. The request stays unchanged for the caller to observe.
        if type(authorization) is not NoAuthorization:
            raise _unsupported_authorization_error()
        if context_value.body_signing_mode != "none":
            raise _unsupported_body_signing_error()
        del request_value


def _unsupported_authorization_error() -> ModelInteractionError:
    """Create the failure for a decision this handler does not own."""
    return ModelInteractionError(
        category=_AUTHENTICATION_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_UNSUPPORTED_AUTHORIZATION_CODE,
        message=_UNSUPPORTED_AUTHORIZATION_MESSAGE,
    )


def _unsupported_body_signing_error() -> ModelInteractionError:
    """Create the failure for a signing mode no-authorization cannot apply."""
    # The selected mode is a closed vocabulary and is not copied into the
    # message, matching the other authentication failures.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_AUTHENTICATION_PHASE,
        code=_UNSUPPORTED_BODY_SIGNING_CODE,
        message=_UNSUPPORTED_BODY_SIGNING_MESSAGE,
    )
