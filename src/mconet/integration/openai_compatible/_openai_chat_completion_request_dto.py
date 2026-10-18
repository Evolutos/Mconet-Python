"""Wire representation of one OpenAI-compatible chat completion request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import JsonValue, validate_json_value_numbers
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)


@dataclass(frozen=True, slots=True)
class OpenAIChatCompletionRequestDTO:
    """Hold the complete request body before payload encoding.

    Optional members are ``None`` when the request does not send them, so the
    service default applies. ``stream`` is ``False`` for a unary request and
    ``True`` for a server stream. The value carries no other member, because
    the request profile forbids unknown members.
    """

    model: str
    """Provider-facing model name sent exactly as configured."""

    messages: tuple[OpenAIChatMessageDTO, ...]
    """Conversation messages in send order."""

    temperature: float | None = None
    """Sampling temperature, or ``None`` to omit the member."""

    top_p: float | None = None
    """Nucleus sampling mass, or ``None`` to omit the member."""

    max_tokens: int | None = None
    """Output token limit, or ``None`` to omit the member."""

    stop: tuple[str, ...] | None = None
    """Stop sequences in order, or ``None`` to omit the member."""

    seed: int | None = None
    """Deterministic sampling seed, or ``None`` to omit the member."""

    tools: tuple[dict[str, JsonValue], ...] | None = None
    """Function tools, or ``None`` to omit the member."""

    tool_choice: JsonValue | None = None
    """Tool selection control, or ``None`` to omit the member."""

    stream: bool = False
    """Whether the service should reply with a server-sent event stream."""

    def __post_init__(self) -> None:
        """Require wire-representable members before any payload is built."""
        model = cast(object, self.model)
        messages = cast(object, self.messages)
        stop = cast(object, self.stop)

        if not isinstance(model, str):
            raise TypeError("OpenAIChatCompletionRequestDTO model must be a string.")

        # The service requires at least one message. A tuple fixes send order
        # so the encoded body cannot change after this value is built.
        if not isinstance(messages, tuple):
            raise TypeError("OpenAIChatCompletionRequestDTO messages must be a tuple.")
        message_values = cast(tuple[object, ...], messages)
        if not message_values:
            raise ValueError(
                "OpenAIChatCompletionRequestDTO messages must not be empty."
            )
        if any(not isinstance(item, OpenAIChatMessageDTO) for item in message_values):
            raise TypeError(
                "OpenAIChatCompletionRequestDTO messages must contain "
                "OpenAIChatMessageDTO values."
            )

        # bool is an int subclass in Python but a different JSON kind, so exact
        # type checks keep True from being sent as a number.
        for name, value in (
            ("temperature", cast(object, self.temperature)),
            ("top_p", cast(object, self.top_p)),
        ):
            if value is not None and type(value) not in (int, float):
                raise TypeError(
                    f"OpenAIChatCompletionRequestDTO {name} must be a number or None."
                )
        for name, value in (
            ("max_tokens", cast(object, self.max_tokens)),
            ("seed", cast(object, self.seed)),
        ):
            if value is not None and type(value) is not int:
                raise TypeError(
                    f"OpenAIChatCompletionRequestDTO {name} must be an integer or None."
                )

        # An empty tuple would encode as [] and still send the member, which is
        # not the same request as omitting it. None is the only way to omit.
        if stop is not None:
            if not isinstance(stop, tuple):
                raise TypeError(
                    "OpenAIChatCompletionRequestDTO stop must be a tuple or None."
                )
            stop_values = cast(tuple[object, ...], stop)
            if not stop_values:
                raise ValueError(
                    "OpenAIChatCompletionRequestDTO stop must not be empty; "
                    "use None to omit it."
                )
            if any(not isinstance(item, str) for item in stop_values):
                raise TypeError(
                    "OpenAIChatCompletionRequestDTO stop must contain only strings."
                )

        tools = cast(object, self.tools)
        # Same omission rule as stop: None leaves the member out, and an empty
        # tuple would send [] rather than omitting tools.
        if tools is not None:
            if not isinstance(tools, tuple) or not tools:
                raise TypeError(
                    "OpenAIChatCompletionRequestDTO tools must be a non-empty "
                    "tuple or None."
                )
            # Each tool is already a JSON object. A domain FunctionTool would
            # not encode until the adapter spelled it.
            if any(
                not isinstance(item, dict) for item in cast(tuple[object, ...], tools)
            ):
                raise TypeError(
                    "OpenAIChatCompletionRequestDTO tools must contain JSON objects."
                )
        tool_choice = cast(object, self.tool_choice)
        # The wire value is a mode string or the named-function object. Other
        # JSON kinds are not a tool_choice.
        if tool_choice is not None and not isinstance(tool_choice, (str, dict)):
            raise TypeError(
                "OpenAIChatCompletionRequestDTO tool_choice must be a string, "
                "object, or None."
            )

        if type(cast(object, self.stream)) is not bool:
            raise TypeError("OpenAIChatCompletionRequestDTO stream must be a bool.")

        # Non-finite floats and integers outside the interoperable range have
        # no portable JSON encoding, so they fail here rather than at encoding.
        for value in (self.temperature, self.top_p, self.max_tokens, self.seed):
            if value is not None:
                validate_json_value_numbers(value)
        if self.tools is not None:
            # Tool schemas can contain numbers. They must be portable before
            # the body is encoded.
            validate_json_value_numbers(list(self.tools))
        if self.tool_choice is not None:
            # A named choice is an object. A mode string has no numbers, so
            # this check only rejects a non-portable number inside the object.
            validate_json_value_numbers(self.tool_choice)

    def to_json(self) -> dict[str, JsonValue]:
        """Return the request body members in frozen profile order.

        Returns:
            A fresh JSON object. Omitted optional members are absent rather than
            ``null``. ``stream`` is the value stored on this request.
        """
        body: dict[str, JsonValue] = {
            "model": self.model,
            "messages": [message.to_json() for message in self.messages],
        }
        # Insertion order follows the frozen profile so the encoded bytes are
        # stable across platforms for the same request.
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.top_p is not None:
            body["top_p"] = self.top_p
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        if self.stop is not None:
            body["stop"] = list(self.stop)
        if self.seed is not None:
            body["seed"] = self.seed
        if self.tools is not None:
            # A fresh list keeps the encoded body independent of the stored
            # tuple while preserving declaration order.
            body["tools"] = list(self.tools)
        if self.tool_choice is not None:
            # The member is inserted before stream so the body order matches
            # the frozen request profile.
            body["tool_choice"] = self.tool_choice
        body["stream"] = self.stream
        return body
