"""Default selection of one authorization handler from a closed candidate set."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.body_signing_requirement import (
    BodySigningMode,
    BodySigningRequirement,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.resolved_authorization_handler import ResolvedAuthorizationHandler

_AUTHENTICATION_CATEGORY = ErrorCategory(OpenIdentifier("authentication"))
_AUTHORIZATION_RESOLUTION_PHASE = InteractionPhase(
    OpenIdentifier("authorization_resolution")
)
_UNSUPPORTED_AUTHORIZATION_CODE = "unsupported_authorization"
_UNSUPPORTED_AUTHORIZATION_MESSAGE = "No authorization handler supports this decision."
_AMBIGUOUS_HANDLER_CODE = "ambiguous_authorization_handler"
_AMBIGUOUS_HANDLER_MESSAGE = (
    "More than one authorization handler supports this decision."
)
_RESOLVER_NAME = "default-authorization-handler-resolver"
_RESOLVER_VERSION = "1.0.0"

DEFAULT_AUTHORIZATION_HANDLER_RESOLVER_DESCRIPTOR = ComponentDescriptor(
    _RESOLVER_NAME,
    _RESOLVER_VERSION,
    "builtin",
)
"""Shared diagnostic metadata for the default authorization handler resolver."""


class DefaultAuthorizationHandlerResolver:
    """Select the one handler that supports an authorization decision.

    Every candidate is asked which signing modes it can apply. Zero matches and
    more than one match fail. A single match returns that same instance and the
    requirement's most preferred shared mode. Candidate order is not a
    tie-breaker.

    Resolution does not reveal credentials, call ``apply``, mutate a request,
    or perform network I/O.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared builtin diagnostic metadata."""
        return DEFAULT_AUTHORIZATION_HANDLER_RESOLVER_DESCRIPTOR

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Return the unique compatible handler and signing mode.

        Args:
            authorization: Opaque authorization decision to match.
            body_signing_requirement: Protocol signing constraint.
            handlers: Closed candidate tuple for this interaction.

        Returns:
            The one matching handler instance and its preferred shared mode.

        Raises:
            TypeError: If an argument or a candidate support result has the
                wrong nominal type.
            ModelInteractionError: If no candidate matches, or if more than one
                candidate matches. The codes are ``unsupported_authorization``
                and ``ambiguous_authorization_handler``.
        """
        authorization_value = cast(object, authorization)
        requirement = cast(object, body_signing_requirement)
        handler_values = cast(object, handlers)
        if not isinstance(authorization_value, Authorization):
            raise TypeError("authorization must implement Authorization.")
        if not isinstance(requirement, BodySigningRequirement):
            raise TypeError(
                "body_signing_requirement must be a BodySigningRequirement."
            )
        if not isinstance(handler_values, tuple):
            raise TypeError("handlers must be a tuple.")

        # Inspect the whole closed set. Stopping at the first match would make
        # a later duplicate depend on tuple order.
        matches: list[tuple[AuthorizationHandler, BodySigningMode]] = []
        for candidate in cast(tuple[object, ...], handler_values):
            if not isinstance(candidate, AuthorizationHandler):
                raise TypeError("handlers must contain AuthorizationHandler values.")
            mode = _preferred_mode(
                _supported_modes(candidate, authorization_value, requirement),
                requirement,
            )
            if mode is not None:
                matches.append((candidate, mode))

        if not matches:
            raise _unsupported_authorization_error()
        if len(matches) > 1:
            raise _ambiguous_handler_error()
        handler, mode = matches[0]
        return ResolvedAuthorizationHandler(handler, mode)


def _supported_modes(
    handler: AuthorizationHandler,
    authorization: Authorization,
    requirement: BodySigningRequirement,
) -> frozenset[BodySigningMode]:
    """Return one handler's declared modes without calling ``apply``."""
    supported = cast(object, handler.supports(authorization, requirement))
    if not isinstance(supported, frozenset):
        raise TypeError("Authorization handler supports() must return a frozenset.")
    return cast(frozenset[BodySigningMode], supported)


def _preferred_mode(
    supported: frozenset[BodySigningMode],
    requirement: BodySigningRequirement,
) -> BodySigningMode | None:
    """Return the requirement's first mode that this handler also accepts."""
    for mode in requirement.acceptable_modes:
        if mode in supported:
            return mode
    return None


def _unsupported_authorization_error() -> ModelInteractionError:
    """Create the failure for a candidate set with no compatible handler."""
    # Candidate names and authorization content stay out of the error. Either
    # can be caller-controlled text.
    return ModelInteractionError(
        category=_AUTHENTICATION_CATEGORY,
        phase=_AUTHORIZATION_RESOLUTION_PHASE,
        code=_UNSUPPORTED_AUTHORIZATION_CODE,
        message=_UNSUPPORTED_AUTHORIZATION_MESSAGE,
    )


def _ambiguous_handler_error() -> ModelInteractionError:
    """Create the failure for more than one compatible handler."""
    return ModelInteractionError(
        category=_AUTHENTICATION_CATEGORY,
        phase=_AUTHORIZATION_RESOLUTION_PHASE,
        code=_AMBIGUOUS_HANDLER_CODE,
        message=_AMBIGUOUS_HANDLER_MESSAGE,
    )
