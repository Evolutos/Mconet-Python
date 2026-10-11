"""Wire representation of one OpenAI-compatible chat message."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue
from mconet.integration.openai_compatible._wire import (
    require_object,
    require_string,
    snapshot_extensions,
    unknown_members,
)

_KNOWN_MEMBERS = frozenset(("role", "content"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a message built from domain data."""
    return snapshot_extensions({}, "OpenAIChatMessageDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatMessageDTO:
    """Hold one ``{"role", "content"}`` chat message exactly as it travels.

    ``role`` keeps the wire spelling and ``content`` keeps the text without
    trimming or normalization. ``extensions`` holds members a response carried
    beyond the frozen shape. They are captured for observation only and are
    never written back, because the request profile forbids unknown members.
    """

    role: str
    """Wire role spelling such as ``system``, ``user``, or ``assistant``."""

    content: str
    """Message text exactly as sent or received."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only response members outside the frozen message shape."""

    def __post_init__(self) -> None:
        """Require string fields and freeze captured extension members."""
        role = cast(object, self.role)
        content = cast(object, self.content)

        # Both fields are required and not nullable in the frozen profile.
        # Role support is decided by the role mapping, not by this carrier.
        if not isinstance(role, str):
            raise TypeError("OpenAIChatMessageDTO role must be a string.")
        if not isinstance(content, str):
            raise TypeError("OpenAIChatMessageDTO content must be a string.")

        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "OpenAIChatMessageDTO"),
        )

    def to_json(self) -> dict[str, JsonValue]:
        """Return the request message members in frozen profile order."""
        # Extensions are deliberately omitted: a request may contain only the
        # frozen members, whatever a previous response carried.
        return {"role": self.role, "content": self.content}

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
        content = require_string(document, "content", path)
        return cls(role, content, unknown_members(document, _KNOWN_MEMBERS))
