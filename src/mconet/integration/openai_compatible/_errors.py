"""Mapping of OpenAI-compatible failure bodies to normalized errors."""

from __future__ import annotations

from mconet.core.domain import (
    Duration,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
    RecoveryHint,
    validate_duration,
)
from mconet.core.spi import TransportResponseMetadata
from mconet.integration.openai_compatible.openai_chat_completion_error_response_dto import (
    OpenAIChatCompletionErrorResponseDTO,
)

SERVICE_AUTHENTICATION_FAILED_CODE = "service_authentication_failed"
"""Stable code for a 401 response."""

SERVICE_PERMISSION_DENIED_CODE = "service_permission_denied"
"""Stable code for a 403 response."""

SERVICE_RATE_LIMITED_CODE = "service_rate_limited"
"""Stable code for a 429 response."""

SERVICE_CONTENT_FILTERED_CODE = "service_content_filtered"
"""Stable code for a failure whose service code is ``content_filter``."""

SERVICE_ERROR_CODE = "service_error"
"""Stable code for any other recognized failure body."""

_RESPONSE_PARSING = InteractionPhase(OpenIdentifier("response_parsing"))
_AUTHENTICATION = ErrorCategory(OpenIdentifier("authentication"))
_PERMISSION = ErrorCategory(OpenIdentifier("permission"))
_RATE_LIMIT = ErrorCategory(OpenIdentifier("rate_limit"))
_CONTENT_FILTER = ErrorCategory(OpenIdentifier("content_filter"))
_MODEL_SERVICE = ErrorCategory(OpenIdentifier("model_service"))

_CONTENT_FILTER_SERVICE_CODE = "content_filter"
_INSUFFICIENT_QUOTA = "insufficient_quota"
_RETRY_AFTER_HEADER = "Retry-After"

# A rejected request was not processed. Other failures may have happened after
# processing started, so their state stays unknown.
_NOT_TRANSIENT_UNPROCESSED = RecoveryHint(False, None, False)


def service_error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Return the normalized error for one recognized failure body.

    Precedence is 401, 403, 429, then a ``content_filter`` service code, then
    the generic model service error. Every error uses a fixed SDK message: the
    service message can echo request content or account details, so it is
    never copied. The HTTP status, the service error code as text, and the
    transport request id are carried for diagnostics.

    Args:
        body: Decoded failure body.
        metadata: Transport facts of the failed response.

    Returns:
        The normalized error, in phase ``response_parsing``.
    """
    status = metadata.status_code
    if status == 401:
        return authentication_error(body, metadata)
    if status == 403:
        return permission_error(body, metadata)
    if status == 429:
        return rate_limit_error(body, metadata)
    if body.error.code == _CONTENT_FILTER_SERVICE_CODE:
        return content_filter_error(body, metadata)
    return model_service_error(body, metadata)


def authentication_error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Return the error for rejected credentials; retrying cannot help."""
    return _error(
        body,
        metadata,
        _AUTHENTICATION,
        SERVICE_AUTHENTICATION_FAILED_CODE,
        "The model service rejected the request credentials.",
        _NOT_TRANSIENT_UNPROCESSED,
    )


def permission_error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Return the error for valid credentials without permission."""
    return _error(
        body,
        metadata,
        _PERMISSION,
        SERVICE_PERMISSION_DENIED_CODE,
        "The model service denied permission for the request.",
        _NOT_TRANSIENT_UNPROCESSED,
    )


def rate_limit_error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Return the error for an exceeded rate limit or quota.

    A rate limit clears with time, so it is transient and carries the
    ``Retry-After`` delay when the service sent one. An exhausted quota,
    reported as ``insufficient_quota`` in ``code`` or ``type``, does not clear
    by waiting, so it is not transient.
    """
    error = body.error
    exhausted = _INSUFFICIENT_QUOTA in (error.code, error.type)
    recovery = (
        _NOT_TRANSIENT_UNPROCESSED
        if exhausted
        else RecoveryHint(True, _retry_after(metadata), False)
    )
    return _error(
        body,
        metadata,
        _RATE_LIMIT,
        SERVICE_RATE_LIMITED_CODE,
        "The model service rate limit or quota was exceeded.",
        recovery,
    )


def content_filter_error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Return the error for content the service's filter blocked.

    The same content is blocked again, so it is not transient. The filter may
    have run on generated output, so processing state is unknown.
    """
    return _error(
        body,
        metadata,
        _CONTENT_FILTER,
        SERVICE_CONTENT_FILTERED_CODE,
        "The model service blocked the request or response content.",
        RecoveryHint(False),
    )


def model_service_error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Return the error for any other recognized failure.

    A 5xx status is a service-side fault and is transient, with the
    ``Retry-After`` delay when sent. Any other status is not transient.
    Processing state is unknown in both cases.
    """
    status = metadata.status_code
    transient = status is not None and 500 <= status <= 599
    return _error(
        body,
        metadata,
        _MODEL_SERVICE,
        SERVICE_ERROR_CODE,
        "The model service returned an error.",
        RecoveryHint(transient, _retry_after(metadata) if transient else None),
    )


def _error(
    body: OpenAIChatCompletionErrorResponseDTO,
    metadata: TransportResponseMetadata,
    category: ErrorCategory,
    code: str,
    message: str,
    recovery: RecoveryHint,
) -> ModelInteractionError:
    """Assemble one normalized error with the shared diagnostic fields."""
    service_code = body.error.code
    return ModelInteractionError(
        category=category,
        phase=_RESPONSE_PARSING,
        code=code,
        message=message,
        status_code=metadata.status_code,
        # Integer codes are kept as their decimal text so the field type is
        # the same for every service.
        service_error_code=None if service_code is None else str(service_code),
        request_id=metadata.request_id,
        recovery=recovery,
    )


def _retry_after(metadata: TransportResponseMetadata) -> Duration | None:
    """Return the ``Retry-After`` delay in its delta-seconds form.

    Only a single field of ASCII digits is used. The HTTP-date form would need
    the current time, and repeated or malformed fields have no single meaning,
    so all of those give ``None`` rather than a guessed delay.
    """
    values = metadata.headers.get_all(_RETRY_AFTER_HEADER)
    if len(values) != 1:
        return None
    text = values[0].strip(" \t")
    if not text.isascii() or not text.isdigit():
        return None
    try:
        return validate_duration(int(text), "seconds")
    except ValueError:
        return None
