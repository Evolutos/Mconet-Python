"""Runtime scheduling for a normalized service-error parse."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata

_MODEL_SERVICE = ErrorCategory(OpenIdentifier("model_service"))
_PROTOCOL = ErrorCategory(OpenIdentifier("protocol"))
_PARSING = InteractionPhase(OpenIdentifier("response_parsing"))
_UNRECOGNIZED_CODE = "unrecognized_service_error"
_UNRECOGNIZED_MESSAGE = "The service error could not be recognized."
_PARSING_FAILED_CODE = "service_error_parsing_failed"
_PARSING_FAILED_MESSAGE = "The service error could not be parsed."


def parse_service_error(
    components: InteractionExecutionComponents,
    payload: ErasedRuntimeValue,
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Parse a decoded service error with the frozen adapter.

    ``parse_error`` is called once. A returned ``ModelInteractionError`` is
    preserved by identity. ``None`` means the adapter does not recognize the
    payload, so this stage builds one fallback error from transport status and
    request id only. A ``ModelInteractionError`` raised by the adapter is
    re-raised by identity. Any other failure becomes one stable parsing error
    whose message does not include the payload. ``parse_response`` is not
    called.

    Args:
        components: Frozen snapshot whose adapter parses the error.
        payload: Decoded service-error payload.
        metadata: Transport facts of the failed response.

    Returns:
        The normalized service error from that single parse.

    Raises:
        TypeError: If an argument, the adapter, or its result has an invalid
            type.
        ModelInteractionError: If parsing fails unexpectedly. That failure
            uses ``service_error_parsing_failed``.
    """
    components_value = cast(object, components)
    payload_value = cast(object, payload)
    metadata_value = cast(object, metadata)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(payload_value, ErasedRuntimeValue):
        raise TypeError("payload must be an ErasedRuntimeValue.")
    if not isinstance(metadata_value, TransportResponseMetadata):
        raise TypeError("metadata must be a TransportResponseMetadata.")

    adapter = cast(object, components_value.task_protocol_adapter)
    if not isinstance(adapter, TaskProtocolAdapter):
        raise TypeError("task_protocol_adapter must implement TaskProtocolAdapter.")
    try:
        parsed = adapter.parse_error(payload_value, metadata_value)
    except ModelInteractionError:
        raise
    except BaseException as error:
        raise ModelInteractionError(
            category=_PROTOCOL,
            phase=_PARSING,
            code=_PARSING_FAILED_CODE,
            message=_PARSING_FAILED_MESSAGE,
            cause=error,
        ) from error

    if parsed is None:
        return _unrecognized_service_error(metadata_value)
    parsed_value = cast(object, parsed)
    if not isinstance(parsed_value, ModelInteractionError):
        raise TypeError("parse_error must return a ModelInteractionError or None.")
    return parsed_value


def _unrecognized_service_error(
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Build the fallback error when the adapter cannot interpret the body."""
    # Status and request id are transport facts. The payload and headers stay
    # out of the message so a service body cannot leak into the normalized error.
    return ModelInteractionError(
        category=_MODEL_SERVICE,
        phase=_PARSING,
        code=_UNRECOGNIZED_CODE,
        message=_UNRECOGNIZED_MESSAGE,
        status_code=metadata.status_code,
        request_id=metadata.request_id,
    )
