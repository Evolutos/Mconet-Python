"""Runtime scheduling for one authorization handler application."""

from __future__ import annotations

import re
from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.authorization_handler import AuthorizationHandler
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.resolved_authorization_handler import ResolvedAuthorizationHandler

_HEADER_NAME_PATTERN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_AUTHENTICATION = InteractionPhase(OpenIdentifier("authentication"))
_INVALID_NAME_CODE = "invalid_authorization_header_name"
_INVALID_NAME_MESSAGE = "Authorization header name is not an HTTP token."
_INVALID_VALUE_CODE = "invalid_authorization_header_value"
_INVALID_VALUE_MESSAGE = "Authorization header value contains a control character."


async def apply_authorization_handler(
    resolved: ResolvedAuthorizationHandler,
    authorization: Authorization,
    context: AuthorizationContext,
    request: MutableTransportRequest,
) -> MutableTransportRequest:
    """Apply the selected handler to the open request, then check its headers.

    ``apply`` is called once. The handler may change only that mutable request.
    Every header name and value is then checked. An illegal name or a control
    character fails the interaction. This stage does not freeze the request or
    send it.

    Args:
        resolved: Handler and signing mode already selected for this decision.
        authorization: Opaque decision supplied to that handler.
        context: Non-sensitive facts supplied to that handler.
        request: Open authorization window for this interaction.

    Returns:
        The same open request after the handler and the header check.

    Raises:
        TypeError: If an argument or the selected handler has an invalid type.
        ModelInteractionError: If the handler fails, or if a header name or
            value is illegal.
    """
    resolved_value = cast(object, resolved)
    authorization_value = cast(object, authorization)
    context_value = cast(object, context)
    request_value = cast(object, request)
    if not isinstance(resolved_value, ResolvedAuthorizationHandler):
        raise TypeError("resolved must be a ResolvedAuthorizationHandler.")
    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")
    if not isinstance(context_value, AuthorizationContext):
        raise TypeError("context must be an AuthorizationContext.")
    if not isinstance(request_value, MutableTransportRequest):
        raise TypeError("request must be a MutableTransportRequest.")

    handler = cast(object, resolved_value.handler)
    if not isinstance(handler, AuthorizationHandler):
        raise TypeError("resolved handler must implement AuthorizationHandler.")
    # One application. A failure is not retried and does not reach transport.
    await handler.apply(authorization_value, context_value, request_value)
    _validate_headers(request_value)
    return request_value


def _validate_headers(request: MutableTransportRequest) -> None:
    """Reject a header the handler wrote that cannot be sent."""
    for field in request.headers.values:
        # The same token and control rules used by authorization decisions.
        # Runtime cannot import the auth package, so the check lives here.
        if _HEADER_NAME_PATTERN.fullmatch(field.name) is None:
            raise _header_error(_INVALID_NAME_CODE, _INVALID_NAME_MESSAGE)
        if any(
            ord(character) < 32 or ord(character) == 127 for character in field.value
        ):
            raise _header_error(_INVALID_VALUE_CODE, _INVALID_VALUE_MESSAGE)


def _header_error(code: str, message: str) -> ModelInteractionError:
    """Create a stable header failure that omits the header text."""
    return ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_AUTHENTICATION,
        code=code,
        message=message,
    )
