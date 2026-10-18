"""Wire representation of one OpenAI-compatible chat message."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue
from mconet.integration.openai_compatible._tool_calls import (
    WireToolCall,
    parse_tool_calls,
)
from mconet.integration.openai_compatible._wire import (
    child_path,
    invalid_protocol_response,
    optional_string,
    require_object,
    require_string,
    snapshot_extensions,
    unknown_members,
)

_KNOWN_MEMBERS = frozenset(("role", "content", "name", "tool_calls", "tool_call_id"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a message built from domain data."""
    return snapshot_extensions({}, "OpenAIChatMessageDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatMessageDTO:
    """Hold one chat message exactly as it travels.

    ``role`` keeps the wire spelling. ``content`` keeps the text without
    trimming or normalization, or is ``None`` when the service sent JSON null,
    which is how an assistant tool-call message often arrives. ``tool_calls``
    and ``tool_call_id`` are the frozen tool members. ``extensions`` holds
    other members a response carried. Extensions are captured for observation
    only and are never written back, because the request profile forbids
    unknown members.
    """

    role: str
    """Wire role spelling such as ``system``, ``user``, ``assistant``, or ``tool``."""

    content: str | None
    """Message text, or ``None`` when the wire member is JSON null."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only response members outside the frozen message shape."""

    tool_calls: tuple[WireToolCall, ...] | None = None
    """Function calls on an assistant message, or ``None`` when omitted."""

    tool_call_id: str | None = None
    """Invocation identity on a tool-result message, or ``None`` when omitted."""

    name: str | None = None
    """Optional function name on a tool-result message."""

    def __post_init__(self) -> None:
        """Require string fields and freeze captured extension members."""
        role = cast(object, self.role)
        content = cast(object, self.content)
        tool_calls = cast(object, self.tool_calls)
        tool_call_id = cast(object, self.tool_call_id)
        name = cast(object, self.name)

        # Role support is decided by the role mapping, not by this carrier.
        # Content may be null when the message carries tool calls.
        if not isinstance(role, str):
            raise TypeError("OpenAIChatMessageDTO role must be a string.")
        if content is not None and not isinstance(content, str):
            raise TypeError("OpenAIChatMessageDTO content must be a string or None.")
        if tool_calls is not None:
            # None omits the member. An empty tuple would encode as [], which
            # the profile rejects.
            if not isinstance(tool_calls, tuple) or not tool_calls:
                raise TypeError(
                    "OpenAIChatMessageDTO tool_calls must be a non-empty tuple or None."
                )
            # Each item is already a decoded call. A raw JSON object would skip
            # the string checks that WireToolCall applies.
            if any(
                not isinstance(item, WireToolCall)
                for item in cast(tuple[object, ...], tool_calls)
            ):
                raise TypeError(
                    "OpenAIChatMessageDTO tool_calls must contain WireToolCall values."
                )
        # tool_call_id and name belong to tool-result messages. Assistant
        # messages leave both unset.
        if tool_call_id is not None and not isinstance(tool_call_id, str):
            raise TypeError(
                "OpenAIChatMessageDTO tool_call_id must be a string or None."
            )
        if name is not None and not isinstance(name, str):
            raise TypeError("OpenAIChatMessageDTO name must be a string or None.")

        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "OpenAIChatMessageDTO"),
        )

    def to_json(self) -> dict[str, JsonValue]:
        """Return the request message members in frozen profile order."""
        # Extensions are deliberately omitted: a request may contain only the
        # frozen members, whatever a previous response carried. Null content
        # is sent as JSON null rather than omitted, because the profile
        # requires the member.
        body: dict[str, JsonValue] = {"role": self.role, "content": self.content}
        if self.name is not None:
            body["name"] = self.name
        if self.tool_calls is not None:
            # Calls follow name so a tool-result name stays beside role and
            # content, matching the profile member order.
            body["tool_calls"] = [call.to_json() for call in self.tool_calls]
        if self.tool_call_id is not None:
            # The id is sent only on a tool-result message. Omitting it when
            # unset keeps an assistant message inside the frozen shape.
            body["tool_call_id"] = self.tool_call_id
        return body

    @classmethod
    def from_json(cls, value: JsonValue, path: str = "") -> OpenAIChatMessageDTO:
        """Read one decoded message object.

        Args:
            value: Decoded JSON for the message.
            path: JSON Pointer of the message, used only in failure messages.

        Returns:
            The message with any unknown members captured as extensions.

        Raises:
            ModelInteractionError: If the value is not an object or a required
                member is missing, null, or not a string.
        """
        document = require_object(value, path)
        role = require_string(document, "role", path)
        content = _content(document, path)
        return cls(
            role,
            content,
            # Known tool members are parsed into fields. Anything else stays
            # in extensions and is not written back onto a later request.
            unknown_members(document, _KNOWN_MEMBERS),
            tool_calls=parse_tool_calls(document, path),
            tool_call_id=optional_string(document, "tool_call_id", path),
            name=optional_string(document, "name", path),
        )


def _content(document: dict[str, JsonValue], path: str) -> str | None:
    """Return message content, treating JSON null as no text."""
    # The member is required. Null is the tool-call shape; any other kind is
    # not text and is not guessed into a string.
    member = child_path(path, "content")
    if "content" not in document:
        raise invalid_protocol_response(member, "must be a string or null")
    value = document["content"]
    if value is None:
        return None
    if not isinstance(value, str):
        raise invalid_protocol_response(member, "must be a string or null")
    return value
