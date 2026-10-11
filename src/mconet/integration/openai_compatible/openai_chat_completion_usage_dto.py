"""Wire representation of OpenAI-compatible token usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue
from mconet.integration.openai_compatible._wire import (
    optional_count,
    require_object,
    snapshot_extensions,
    unknown_members,
)

_KNOWN_MEMBERS = frozenset(("prompt_tokens", "completion_tokens", "total_tokens"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for directly built usage."""
    return snapshot_extensions({}, "OpenAIChatCompletionUsageDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatCompletionUsageDTO:
    """Hold the decoded ``usage`` object of a successful response.

    Each count is independently optional. ``None`` means the service did not
    send the member, and zero is an explicit count. ``total_tokens`` is kept as
    reported, never computed. Breakdown members such as
    ``prompt_tokens_details`` are captured in ``extensions``.
    """

    prompt_tokens: int | None = None
    """Input token count, or ``None`` when the service did not send it."""

    completion_tokens: int | None = None
    """Output token count, or ``None`` when the service did not send it."""

    total_tokens: int | None = None
    """Reported total, or ``None`` when the service did not send it."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only usage members outside the frozen shape."""

    def __post_init__(self) -> None:
        """Require optional non-negative counts and freeze captured extensions."""
        for name, value in (
            ("prompt_tokens", cast(object, self.prompt_tokens)),
            ("completion_tokens", cast(object, self.completion_tokens)),
            ("total_tokens", cast(object, self.total_tokens)),
        ):
            if value is None:
                continue
            # Exact int membership keeps JSON booleans from becoming counts.
            if type(value) is not int:
                raise TypeError(
                    f"OpenAIChatCompletionUsageDTO {name} must be an integer or None."
                )
            if value < 0:
                raise ValueError(
                    f"OpenAIChatCompletionUsageDTO {name} must not be negative."
                )

        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "OpenAIChatCompletionUsageDTO"),
        )

    @classmethod
    def from_json(
        cls, value: JsonValue, path: str = ""
    ) -> OpenAIChatCompletionUsageDTO:
        """Read one decoded usage object.

        Args:
            value: Decoded JSON for the usage object.
            path: JSON Pointer of the usage object, used only in failure messages.

        Returns:
            The usage counts with any unknown members captured as extensions.

        Raises:
            ModelInteractionError: If the value is not an object, or a present
                count is null, negative, or not an integer.
        """
        document = require_object(value, path)
        return cls(
            optional_count(document, "prompt_tokens", path),
            optional_count(document, "completion_tokens", path),
            optional_count(document, "total_tokens", path),
            unknown_members(document, _KNOWN_MEMBERS),
        )
