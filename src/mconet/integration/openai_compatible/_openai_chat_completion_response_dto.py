"""Wire representation of one successful OpenAI-compatible chat completion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue
from mconet.integration.openai_compatible._openai_chat_completion_choice_dto import (
    OpenAIChatCompletionChoiceDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_usage_dto import (
    OpenAIChatCompletionUsageDTO,
)
from mconet.integration.openai_compatible._wire import (
    child_path,
    optional_string,
    require_array,
    require_object,
    snapshot_extensions,
    unknown_members,
)

_KNOWN_MEMBERS = frozenset(("id", "model", "choices", "usage"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a directly built response."""
    return snapshot_extensions({}, "OpenAIChatCompletionResponseDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatCompletionResponseDTO:
    """Hold one decoded successful response body.

    ``choices`` keeps every element in service order. How many choices a result
    may contain is decided by the response mapping, so this value also holds an
    empty or multi-choice body. Members outside the frozen shape, such as
    ``object``, ``created``, and ``system_fingerprint``, are captured in
    ``extensions``.
    """

    choices: tuple[OpenAIChatCompletionChoiceDTO, ...]
    """Decoded choices in the order the service sent them."""

    id: str | None = None
    """Service response identifier, or ``None`` when not sent."""

    model: str | None = None
    """Model name the service reports it used, or ``None`` when not sent."""

    usage: OpenAIChatCompletionUsageDTO | None = None
    """Reported token usage, or ``None`` when not sent."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only response members outside the frozen shape."""

    def __post_init__(self) -> None:
        """Require the frozen member types and freeze captured extensions."""
        choices = cast(object, self.choices)
        response_id = cast(object, self.id)
        model = cast(object, self.model)
        usage = cast(object, self.usage)

        if not isinstance(choices, tuple):
            raise TypeError("OpenAIChatCompletionResponseDTO choices must be a tuple.")
        if any(
            not isinstance(choice, OpenAIChatCompletionChoiceDTO)
            for choice in cast(tuple[object, ...], choices)
        ):
            raise TypeError(
                "OpenAIChatCompletionResponseDTO choices must contain "
                "OpenAIChatCompletionChoiceDTO values."
            )
        for name, value in (("id", response_id), ("model", model)):
            if value is not None and not isinstance(value, str):
                raise TypeError(
                    f"OpenAIChatCompletionResponseDTO {name} must be a string or None."
                )
        if usage is not None and not isinstance(usage, OpenAIChatCompletionUsageDTO):
            raise TypeError(
                "OpenAIChatCompletionResponseDTO usage must be an "
                "OpenAIChatCompletionUsageDTO or None."
            )

        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "OpenAIChatCompletionResponseDTO"),
        )

    @classmethod
    def from_json(cls, value: JsonValue) -> OpenAIChatCompletionResponseDTO:
        """Read one decoded successful response body.

        Args:
            value: Decoded JSON for the complete response body.

        Returns:
            The response with any unknown top-level members captured.

        Raises:
            ModelInteractionError: If the body or any member it contains does
                not have its frozen shape.
        """
        document = require_object(value, "")
        # Members are read in frozen profile order, so the first failure is the
        # same on every platform when several members are wrong.
        response_id = optional_string(document, "id", "")
        model = optional_string(document, "model", "")
        choices_path = child_path("", "choices")
        choices = tuple(
            OpenAIChatCompletionChoiceDTO.from_json(
                choice, child_path(choices_path, index)
            )
            for index, choice in enumerate(require_array(document, "choices", ""))
        )

        # usage is optional, but a present null is rejected by the usage reader
        # because the frozen profile marks it not nullable.
        usage = (
            OpenAIChatCompletionUsageDTO.from_json(
                document["usage"], child_path("", "usage")
            )
            if "usage" in document
            else None
        )
        return cls(
            choices,
            response_id,
            model,
            usage,
            unknown_members(document, _KNOWN_MEMBERS),
        )
