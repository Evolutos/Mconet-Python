"""HTTP status classification for a completed response."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.transport_outcome import TransportOutcome

_SUCCESS_MINIMUM = 200
_SUCCESS_MAXIMUM = 299
_HTTP_STATUS_MINIMUM = 100
_HTTP_STATUS_MAXIMUM = 599
_SUCCESS_OUTCOME = TransportOutcome(OpenIdentifier("success"))
_SERVICE_ERROR_OUTCOME = TransportOutcome(OpenIdentifier("service_error"))
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_INVALID_HTTP_STATUS_CODE = "invalid_http_status"
_INVALID_HTTP_STATUS_MESSAGE = "HTTP status is not a received response status."


@dataclass(frozen=True, slots=True)
class HttpStatusOutcome:
    """Normalized outcome together with the status that produced it.

    The status code is retained exactly. This value does not include a response
    body or an interpretation of a service error payload.
    """

    outcome: TransportOutcome
    """``success`` for 2xx and ``service_error`` for every other received status."""

    status_code: int
    """The received HTTP status code."""

    def __post_init__(self) -> None:
        """Require a real outcome and the status that selected it."""
        outcome = cast(object, self.outcome)
        status_code = cast(object, self.status_code)
        if not isinstance(outcome, TransportOutcome):
            raise TypeError("HttpStatusOutcome outcome must be a TransportOutcome.")
        if type(status_code) is not int:
            raise TypeError("HttpStatusOutcome status_code must be an integer.")
        if not _HTTP_STATUS_MINIMUM <= status_code <= _HTTP_STATUS_MAXIMUM:
            raise ValueError("HttpStatusOutcome status_code must be a received status.")
        if not _SUCCESS_MINIMUM <= status_code <= _SUCCESS_MAXIMUM:
            if outcome != _SERVICE_ERROR_OUTCOME:
                raise ValueError("HttpStatusOutcome classification does not match.")
            return
        if outcome != _SUCCESS_OUTCOME:
            raise ValueError("HttpStatusOutcome classification does not match.")


def map_http_status(status_code: int) -> HttpStatusOutcome:
    """Classify one received HTTP status without reading a response body.

    Codes from 200 through 299 are ``success``. Every other code from 100
    through 599 is ``service_error``. The numeric status is preserved in both
    cases. The function does not follow a redirect or inspect a payload.

    Args:
        status_code: HTTP status code from a completed response.

    Returns:
        The outcome and the same status code.

    Raises:
        TypeError: If ``status_code`` is not an integer. ``bool`` is rejected.
        ModelInteractionError: If ``status_code`` is outside 100 through 599.
            The stable code is ``invalid_http_status``.
    """
    candidate = cast(object, status_code)
    # bool is an int subclass, but it is not an HTTP status code.
    if type(candidate) is not int:
        raise TypeError("status_code must be an integer.")
    if not _HTTP_STATUS_MINIMUM <= candidate <= _HTTP_STATUS_MAXIMUM:
        raise _invalid_http_status_error()
    if _SUCCESS_MINIMUM <= candidate <= _SUCCESS_MAXIMUM:
        return HttpStatusOutcome(_SUCCESS_OUTCOME, candidate)
    return HttpStatusOutcome(_SERVICE_ERROR_OUTCOME, candidate)


def _invalid_http_status_error() -> ModelInteractionError:
    """Create the failure for one value that is not a received HTTP status.

    Returns:
        A transport error that does not include the rejected number.
    """
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_INVALID_HTTP_STATUS_CODE,
        message=_INVALID_HTTP_STATUS_MESSAGE,
    )
