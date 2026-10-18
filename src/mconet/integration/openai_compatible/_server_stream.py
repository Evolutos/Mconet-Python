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
from mconet.core.domain.tool_call_element import ToolCallElement
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


class _PartialToolCall:
    """Accumulate one streamed function call across argument fragments."""

    __slots__ = ("arguments", "call_id", "call_type", "name")

    def __init__(self) -> None:
        self.call_id = ""
        self.call_type = ""
        self.name = ""
        self.arguments = ""

    def complete(self) -> bool:
        """Return whether the call can be exposed as a tool-call element."""
        # A fragment that has not yet named the function or the invocation is
        # kept internally. Emitting it would invent an id the caller cannot cite.
        return bool(
            self.call_id
            and not self.call_id.isspace()
            and self.call_type
            and not self.call_type.isspace()
            and self.name
            and not self.name.isspace()
        )


class OpenAIServerStreamMapper:
    """Map successive chat-completion chunks, assembling tool calls by index.

    One mapper belongs to one interaction. Tool-call fragments that share a
    choice and a call index are concatenated here, so a later event carries
    the calls seen so far rather than one argument fragment.

    Equality compares the mapper kind, not the calls accumulated so far. Two
    fresh plans therefore still describe the same protocol.
    """

    __slots__ = ("_calls",)

    def __init__(self) -> None:
        self._calls: dict[int, dict[int, _PartialToolCall]] = {}

    def __eq__(self, other: object) -> bool:
        """Return whether the other value is the same kind of mapper."""
        return type(other) is OpenAIServerStreamMapper

    def __hash__(self) -> int:
        """Return a hash of the mapper kind."""
        return hash(OpenAIServerStreamMapper)

    def __call__(
        self,
        payload: bytes,
        metadata: TransportResponseMetadata,
    ) -> tuple[ServerStreamEvent, ...]:
        """Return the events contained in one SSE data payload.

        A payload whose top-level member is ``error`` becomes a service error
        and is not returned as an event. Other payloads are chat completion
        chunks. One event is produced for each choice that carries text,
        assembled tool calls, or a finish reason. A role-only delta is skipped.

        Args:
            payload: UTF-8 JSON for one SSE ``data`` payload.
            metadata: Response metadata used when the payload is a service error.

        Returns:
            The chunk events, in choice order. The tuple is empty when every
            choice was only a role marker.

        Raises:
            TypeError: If ``payload`` is not ``bytes``.
            ModelInteractionError: If the payload is not UTF-8 JSON, violates
                the chunk shape, or is a recognized service error.
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
            mapped = self._map_choice(choice, choice_path, response_id, model)
            if mapped is not None:
                events.append(mapped)
        return tuple(events)

    def _map_choice(
        self,
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
        self._merge_tool_calls(index, delta_object, child_path(path, "delta"))
        finish_reason = _finish_reason(document, path)
        # A finish chunk closes the choice. A call that never received an id,
        # type, or name cannot be returned as something the caller can answer.
        if finish_reason is not None:
            self._require_complete_calls(index, child_path(path, "delta"))
        tool_calls = self._assembled_calls(index)
        if text == "" and finish_reason is None and tool_calls is None:
            return None
        return ServerStreamEvent(
            index,
            text,
            finish_reason=finish_reason,
            response_id=response_id,
            model=model,
            tool_calls=tool_calls,
        )

    def _merge_tool_calls(
        self,
        choice_index: int,
        delta: dict[str, JsonValue],
        path: str,
    ) -> None:
        """Fold one delta's tool-call fragments into this choice."""
        # A missing or null member means this chunk has no tool-call update.
        if "tool_calls" not in delta or delta["tool_calls"] is None:
            return
        value = delta["tool_calls"]
        calls_path = child_path(path, "tool_calls")
        if not isinstance(value, list):
            # A single object is not a delta list. The protocol sends an array
            # even when the chunk updates one call.
            raise invalid_protocol_response(calls_path, "must be an array")
        items = cast(list[JsonValue], value)
        for offset, item in enumerate(items):
            item_path = child_path(calls_path, offset)
            if not isinstance(item, dict):
                raise invalid_protocol_response(item_path, "must be an object")
            self._merge_fragment(choice_index, item, item_path)

    def _merge_fragment(
        self,
        choice_index: int,
        item: dict[str, JsonValue],
        path: str,
    ) -> None:
        """Merge one tool-call object into the call selected by its index."""
        raw_index = item.get("index")
        # bool is an int subclass, so the index check is exact. A flag is not
        # a position in the call list.
        if type(raw_index) is not int or raw_index < 0:
            raise invalid_protocol_response(
                child_path(path, "index"), "must be a non-negative integer"
            )
        calls = self._calls.setdefault(choice_index, {})
        partial = calls.setdefault(raw_index, _PartialToolCall())
        call_id = _text_fragment(item, "id", path)
        # An empty fragment does not erase an id or type already received.
        if call_id:
            partial.call_id = call_id
        call_type = _text_fragment(item, "type", path)
        if call_type:
            partial.call_type = call_type
        function = item.get("function")
        if function is None:
            return
        function_path = child_path(path, "function")
        if not isinstance(function, dict):
            raise invalid_protocol_response(function_path, "must be an object")
        # Name and arguments may arrive in pieces. Each present string is
        # appended; an omitted member leaves what earlier chunks already stored.
        name = _text_fragment(function, "name", function_path)
        if name is not None:
            partial.name += name
        arguments = _text_fragment(function, "arguments", function_path)
        if arguments is not None:
            partial.arguments += arguments

    def _require_complete_calls(self, choice_index: int, path: str) -> None:
        """Reject a finished choice that still has an unnamed call."""
        for call_index, partial in self._calls.get(choice_index, {}).items():
            if partial.complete():
                continue
            raise invalid_protocol_response(
                child_path(path, "tool_calls"),
                f"call {call_index} must include an id, type, and function name",
            )

    def _assembled_calls(self, choice_index: int) -> tuple[ToolCallElement, ...] | None:
        """Return the complete calls for one choice, in index order."""
        calls = self._calls.get(choice_index, {})
        assembled = tuple(
            ToolCallElement(
                f"choice-{choice_index}-tool-{call_index}",
                partial.call_id,
                partial.name,
                partial.arguments,
                partial.call_type,
            )
            for call_index, partial in sorted(calls.items())
            if partial.complete()
        )
        # None omits the member. An empty tuple would claim that calls exist
        # when every fragment is still missing its identity.
        return assembled or None


def map_openai_server_stream_payload(
    payload: bytes,
    metadata: TransportResponseMetadata,
) -> tuple[ServerStreamEvent, ...]:
    """Return the events contained in one SSE data payload.

    This uses a fresh mapper, so tool-call fragments are assembled only within
    this payload. A stream that splits one call across payloads must reuse one
    :class:`OpenAIServerStreamMapper`.

    Args:
        payload: UTF-8 JSON for one SSE ``data`` payload.
        metadata: Response metadata used when the payload is a service error.

    Returns:
        The chunk events, in choice order.

    Raises:
        TypeError: If ``payload`` is not ``bytes``.
        ModelInteractionError: If the payload is not UTF-8 JSON, violates the
            chunk shape, or is a recognized service error.
    """
    return OpenAIServerStreamMapper()(payload, metadata)


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


def _text_fragment(
    document: dict[str, JsonValue], member: str, path: str
) -> str | None:
    """Return one string member, or ``None`` when it is absent or null."""
    if member not in document or document[member] is None:
        return None
    value = document[member]
    if not isinstance(value, str):
        raise invalid_protocol_response(child_path(path, member), "must be a string")
    return value


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
