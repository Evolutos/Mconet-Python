"""Runtime scheduling for a successful parsed task response."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.parsed_task_response import ParsedTaskResponse
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.task_protocol_adapter import TaskProtocolAdapter

_PROTOCOL = ErrorCategory(OpenIdentifier("protocol"))
_PARSING = InteractionPhase(OpenIdentifier("response_parsing"))
_PARSING_FAILED_CODE = "response_parsing_failed"
_PARSING_FAILED_MESSAGE = "The successful response could not be parsed."


def parse_successful_task_response(
    components: InteractionExecutionComponents,
    payload: ErasedRuntimeValue,
) -> ParsedTaskResponse:
    """Parse a decoded success payload with the frozen adapter.

    ``parse_response`` is called once. The result must be a
    ``ParsedTaskResponse``. A ``ModelInteractionError`` is returned unchanged.
    Any other failure becomes one stable parsing error whose message does not
    include the payload. ``parse_error`` is not called.

    Args:
        components: Frozen snapshot whose adapter parses the response.
        payload: Decoded successful payload.

    Returns:
        The parsed task response from that single call.

    Raises:
        TypeError: If an argument, the adapter, or its result has an invalid
            type.
        ModelInteractionError: If parsing fails. An unknown failure uses
            ``response_parsing_failed``.
    """
    components_value = cast(object, components)
    payload_value = cast(object, payload)
    if not isinstance(components_value, InteractionExecutionComponents):
        raise TypeError("components must be an InteractionExecutionComponents.")
    if not isinstance(payload_value, ErasedRuntimeValue):
        raise TypeError("payload must be an ErasedRuntimeValue.")

    adapter = cast(object, components_value.task_protocol_adapter)
    if not isinstance(adapter, TaskProtocolAdapter):
        raise TypeError("task_protocol_adapter must implement TaskProtocolAdapter.")
    try:
        parsed = adapter.parse_response(payload_value)
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

    parsed_value = cast(object, parsed)
    if not isinstance(parsed_value, ParsedTaskResponse):
        raise TypeError("parse_response must return a ParsedTaskResponse.")
    return parsed_value
