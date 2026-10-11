"""HTTP method mapping for the system HTTP transport."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

# These tokens are the unary methods this transport will place on a request
# line. CONNECT is a tunnel operation, and TRACE can reflect authorization
# headers, so neither is part of the reviewed surface. Spelling is significant:
# a different case is a different token and is not rewritten onto this set.
_SUPPORTED_HTTP_METHODS = frozenset(
    {
        "DELETE",
        "GET",
        "HEAD",
        "OPTIONS",
        "PATCH",
        "POST",
        "PUT",
    }
)
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_UNSUPPORTED_HTTP_METHOD_CODE = "unsupported_http_method"
_UNSUPPORTED_HTTP_METHOD_MESSAGE = (
    "HTTP method is not supported by the system HTTP transport."
)


def map_http_method(method: str) -> str:
    """Accept one canonical HTTP method for a system HTTP request.

    The returned token is the input when it is an exact member of the
    transport whitelist. The function does not trim, case-fold, or substitute
    another method. It does not read a URL, headers, body, or credentials, and
    it does not open a connection.

    Args:
        method: Protocol method text to validate.

    Returns:
        The same method token, known to be supported by this transport.

    Raises:
        TypeError: If ``method`` is not a string.
        ModelInteractionError: If ``method`` is not an exact whitelist member.
            The stable code is ``unsupported_http_method``. The rejected text
            is omitted from the error.
    """
    candidate = cast(object, method)
    # Membership is defined on exact strings. A non-string must not be coerced
    # into a request-line token through its text representation.
    if not isinstance(candidate, str):
        raise TypeError("method must be a string.")

    # Exact membership keeps the plan's method text unchanged. Case-folding or
    # trimming would send a different token than the execution plan selected.
    if candidate not in _SUPPORTED_HTTP_METHODS:
        raise _unsupported_http_method_error()

    return candidate


def _unsupported_http_method_error() -> ModelInteractionError:
    """Create the content-safe failure for one unsupported method.

    Returns:
        A transport error that does not include the rejected method.
    """
    # The method text is omitted because an untrusted value can contain header
    # injection or other data that must not enter errors, diagnostics, or logs.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_UNSUPPORTED_HTTP_METHOD_CODE,
        message=_UNSUPPORTED_HTTP_METHOD_MESSAGE,
    )
