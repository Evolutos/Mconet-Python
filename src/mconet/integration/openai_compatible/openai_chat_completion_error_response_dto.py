"""Wire representation of one OpenAI-compatible failure response body."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue
from mconet.integration.openai_compatible._wire import (
    child_path,
    require_object,
    snapshot_extensions,
    unknown_members,
)
from mconet.integration.openai_compatible.openai_chat_completion_error_dto import (
    OpenAIChatCompletionErrorDTO,
)

_KNOWN_MEMBERS = frozenset(("error",))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a directly built failure body."""
    return snapshot_extensions({}, "OpenAIChatCompletionErrorResponseDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatCompletionErrorResponseDTO:
    """Hold one decoded failure body of the form ``{"error": {...}}``.

    Top-level members other than ``error`` are captured in ``extensions``.
    """

    error: OpenAIChatCompletionErrorDTO
    """The decoded error object."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only top-level members outside the frozen shape."""

    def __post_init__(self) -> None:
        """Require an error object and freeze captured extensions."""
        if not isinstance(cast(object, self.error), OpenAIChatCompletionErrorDTO):
            raise TypeError(
                "OpenAIChatCompletionErrorResponseDTO error must be an "
                "OpenAIChatCompletionErrorDTO."
            )
        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(
                self.extensions, "OpenAIChatCompletionErrorResponseDTO"
            ),
        )

    @classmethod
    def from_json(cls, value: JsonValue) -> OpenAIChatCompletionErrorResponseDTO:
        """Read one decoded failure body.

        Args:
            value: Decoded JSON for the complete failure body.

        Returns:
            The failure body with any unknown top-level members captured.

        Raises:
            ModelInteractionError: If the body is not an object or its
                required ``error`` member does not have the frozen shape.
        """
        document = require_object(value, "")
        # A missing member is read as null so it fails as "must be an object".
        error = OpenAIChatCompletionErrorDTO.from_json(
            document.get("error"), child_path("", "error")
        )
        return cls(error, unknown_members(document, _KNOWN_MEMBERS))
