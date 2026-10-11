"""Wire representation of one OpenAI-compatible chat completion choice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue
from mconet.integration.openai_compatible._wire import (
    child_path,
    require_count,
    require_object,
    require_string,
    snapshot_extensions,
    unknown_members,
)
from mconet.integration.openai_compatible.openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)

_KNOWN_MEMBERS = frozenset(("index", "message", "finish_reason"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a directly built choice."""
    return snapshot_extensions({}, "OpenAIChatCompletionChoiceDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatCompletionChoiceDTO:
    """Hold one decoded ``choices`` element of a successful response.

    ``finish_reason`` keeps the service's text exactly. Its interpretation as a
    status belongs to the response mapping, so unknown reasons are kept here.
    Members outside the frozen shape, such as ``logprobs``, are captured in
    ``extensions`` and not interpreted.
    """

    index: int
    """Position the service assigned to this choice."""

    message: OpenAIChatMessageDTO
    """Generated message carried by this choice."""

    finish_reason: str
    """Service-reported reason the generation ended."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only choice members outside the frozen shape."""

    def __post_init__(self) -> None:
        """Require the frozen member types and freeze captured extensions."""
        index = cast(object, self.index)
        message = cast(object, self.message)
        finish_reason = cast(object, self.finish_reason)

        if type(index) is not int:
            raise TypeError("OpenAIChatCompletionChoiceDTO index must be an integer.")
        if index < 0:
            raise ValueError(
                "OpenAIChatCompletionChoiceDTO index must not be negative."
            )
        if not isinstance(message, OpenAIChatMessageDTO):
            raise TypeError(
                "OpenAIChatCompletionChoiceDTO message must be an OpenAIChatMessageDTO."
            )
        if not isinstance(finish_reason, str):
            raise TypeError(
                "OpenAIChatCompletionChoiceDTO finish_reason must be a string."
            )

        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "OpenAIChatCompletionChoiceDTO"),
        )

    @classmethod
    def from_json(
        cls, value: JsonValue, path: str = ""
    ) -> OpenAIChatCompletionChoiceDTO:
        """Read one decoded choice object.

        Args:
            value: Decoded JSON for the choice.
            path: JSON Pointer of the choice, used only in failure messages.

        Returns:
            The choice with any unknown members captured as extensions.

        Raises:
            ModelInteractionError: If the value or any required member does not
                have its frozen shape.
        """
        document = require_object(value, path)
        index = require_count(document, "index", path)
        message = OpenAIChatMessageDTO.from_json(
            document.get("message"), child_path(path, "message")
        )
        finish_reason = require_string(document, "finish_reason", path)
        return cls(
            index,
            message,
            finish_reason,
            unknown_members(document, _KNOWN_MEMBERS),
        )
