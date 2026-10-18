"""Map one OpenAI-compatible chat completion chunk to server-stream events."""

from __future__ import annotations

import json
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.server_stream_event import ServerStreamEvent
from mconet.core.spi import TransportResponseMetadata
from mconet.integration.openai_compatible._errors import service_error
from mconet.integration.openai_compatible._openai_chat_completion_error_response_dto import (
    OpenAIChatCompletionErrorResponseDTO,
)
from mconet.integration.openai_compatible._wire import (
    child_path,
    invalid_protocol_response,
    require_array,
    require_count,
    require_object,
)

_DESERIALIZATION = ErrorCategory(OpenIdentifier("deserialization"))
_MAPPING = InteractionPhase(OpenIdentifier("stream_mapping"))
_DESERIALIZATION_CODE = "deserialization"
_DESERIALIZATION_MESSAGE = "A stream event cannot be decoded."


def map_openai_server_stream_payload(
    payload: bytes,
    metadata: TransportResponseMetadata,
) -> tuple[ServerStreamEvent, ...]:
    """Return the events contained in one SSE data payload.

    A payload whose top-level member is ``error`` becomes a service error and
    is not returned as an event. Other payloads are chat completion chunks.
    One event is produced for each choice that carries text or a finish
    reason. A role-only delta is skipped.

    Args:
        payload: UTF-8 JSON for one SSE ``data`` payload.
        metadata: Response metadata used when the payload is a service error.

    Returns:
        The chunk events, in choice order. The tuple is empty when every
        choice was only a role marker.

    Raises:
        TypeError: If ``payload`` is not ``bytes``.
        ModelInteractionError: If the payload is not UTF-8 JSON, violates the
            chunk shape, or is a recognized service error.
    """
    if not isinstance(cast(object, payload), bytes):
        raise TypeError("payload must be bytes.")
    document = _decode_payload(payload)
    # An error object uses the same failure mapping as a non-stream HTTP
    # error, including status-specific categories when the metadata has them.
    if "error" in document:
        body = OpenAIChatCompletionErrorResponseDTO.from_json(document)
        raise service_error(body, metadata)
    choices = require_array(document, "choices", "")
    response_id = _optional_text(document, "id")
    model = _optional_text(document, "model")
    events: list[ServerStreamEvent] = []
    for index, choice in enumerate(choices):
        path = child_path("", "choices")
        choice_path = child_path(path, index)
        mapped = _map_choice(choice, choice_path, response_id, model)
        if mapped is not None:
            events.append(mapped)
    return tuple(events)


def _decode_payload(payload: bytes) -> dict[str, JsonValue]:
    """Decode one payload into a JSON object."""
    # UTF-8 and JSON failures share one deserialization error. The payload can
    # echo the prompt, so neither the bytes nor the parser message is returned.
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _deserialization_error() from error
    try:
        raw = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise _deserialization_error() from error
    try:
        # Portable number checks reject values that cannot round-trip as JSON
        # numbers shared with other SDK languages.
        validate_json_value_numbers(cast(JsonValue, raw))
    except (TypeError, ValueError) as error:
        raise _deserialization_error() from error
    return require_object(cast(JsonValue, raw), "")


def _map_choice(
    value: JsonValue,
    path: str,
    response_id: str | None,
    model: str | None,
) -> ServerStreamEvent | None:
    """Return one choice event, or ``None`` when the choice has no observation."""
    document = require_object(value, path)
    index = require_count(document, "index", path)
    delta = document.get("delta")
    # Chunks carry a delta object rather than a full message. A missing delta
    # is an empty update, not a second response shape.
    if delta is None:
        delta_object: dict[str, JsonValue] = {}
    else:
        delta_object = require_object(delta, child_path(path, "delta"))
    text = _delta_text(delta_object, child_path(path, "delta"))
    finish_reason = _finish_reason(document, path)
    if text == "" and finish_reason is None:
        return None
    return ServerStreamEvent(
        index,
        text,
        finish_reason=finish_reason,
        response_id=response_id,
        model=model,
    )


def _delta_text(delta: dict[str, JsonValue], path: str) -> str:
    """Return the text in a delta, treating a missing or null content as empty."""
    # OpenAI sends null content on the chunk that only carries a finish reason.
    # That chunk is still an event when a finish reason is present.
    if "content" not in delta or delta["content"] is None:
        return ""
    content = delta["content"]
    if not isinstance(content, str):
        raise invalid_protocol_response(child_path(path, "content"), "must be a string")
    return content


def _finish_reason(document: dict[str, JsonValue], path: str) -> str | None:
    """Return the finish reason, treating JSON null as not finished."""
    # A missing or null reason means generation continues. Only a string ends
    # the choice.
    if "finish_reason" not in document or document["finish_reason"] is None:
        return None
    reason = document["finish_reason"]
    if not isinstance(reason, str):
        raise invalid_protocol_response(
            child_path(path, "finish_reason"), "must be a string"
        )
    return reason


def _optional_text(document: dict[str, JsonValue], name: str) -> str | None:
    """Return one optional string member, or ``None`` when it is absent or null."""
    # Response id and model are copied onto every choice event when present.
    # A null member is the same as an omitted member.
    if name not in document or document[name] is None:
        return None
    value = document[name]
    if not isinstance(value, str):
        raise invalid_protocol_response(child_path("", name), "must be a string")
    return value


def _deserialization_error() -> ModelInteractionError:
    """Create the failure for a payload that is not portable JSON text."""
    # The payload can echo the prompt, so the message does not include it.
    return ModelInteractionError(
        category=_DESERIALIZATION,
        phase=_MAPPING,
        code=_DESERIALIZATION_CODE,
        message=_DESERIALIZATION_MESSAGE,
    )
