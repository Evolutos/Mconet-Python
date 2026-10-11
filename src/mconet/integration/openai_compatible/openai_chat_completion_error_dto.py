"""Wire representation of the error object in an OpenAI-compatible failure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import Extensions, JsonValue, validate_json_value_numbers
from mconet.integration.openai_compatible._wire import (
    child_path,
    invalid_protocol_response,
    require_object,
    require_string,
    snapshot_extensions,
    unknown_members,
)

_KNOWN_MEMBERS = frozenset(("message", "type", "code"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a directly built error."""
    return snapshot_extensions({}, "OpenAIChatCompletionErrorDTO")


@dataclass(frozen=True, slots=True)
class OpenAIChatCompletionErrorDTO:
    """Hold the decoded ``error`` object of a failure response body.

    ``message`` is service text. It is kept here only so the wire value is
    complete; SDK errors never copy it. ``type`` and ``code`` may be absent or
    null, and both cases are held as ``None``. Members outside the frozen
    shape, such as ``param``, are captured in ``extensions``.
    """

    message: str
    """Service-provided error description."""

    type: str | None = None
    """Service error type, or ``None`` when absent or null."""

    code: str | int | None = None
    """Service error code as sent, or ``None`` when absent or null."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Read-only error members outside the frozen shape."""

    def __post_init__(self) -> None:
        """Require the frozen member types and freeze captured extensions."""
        message = cast(object, self.message)
        error_type = cast(object, self.type)
        code = cast(object, self.code)

        if not isinstance(message, str):
            raise TypeError("OpenAIChatCompletionErrorDTO message must be a string.")
        if error_type is not None and not isinstance(error_type, str):
            raise TypeError(
                "OpenAIChatCompletionErrorDTO type must be a string or None."
            )
        # Exact int membership keeps JSON booleans from becoming integer codes.
        if code is not None and not isinstance(code, str) and type(code) is not int:
            raise TypeError(
                "OpenAIChatCompletionErrorDTO code must be a string, an integer, "
                "or None."
            )
        if type(code) is int:
            validate_json_value_numbers(code)

        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "OpenAIChatCompletionErrorDTO"),
        )

    @classmethod
    def from_json(
        cls, value: JsonValue, path: str = ""
    ) -> OpenAIChatCompletionErrorDTO:
        """Read one decoded error object.

        Args:
            value: Decoded JSON for the error object.
            path: JSON Pointer of the error object, used only in failure
                messages.

        Returns:
            The error with any unknown members captured as extensions.

        Raises:
            ModelInteractionError: If the value is not an object, ``message``
                is not a string, ``type`` is neither a string nor null, or
                ``code`` is neither a string, an integer, nor null.
        """
        document = require_object(value, path)
        message = require_string(document, "message", path)

        error_type = document.get("type")
        if error_type is not None and not isinstance(error_type, str):
            raise invalid_protocol_response(
                child_path(path, "type"), "must be a string or null"
            )

        code = document.get("code")
        if code is not None and not isinstance(code, str) and type(code) is not int:
            raise invalid_protocol_response(
                child_path(path, "code"), "must be a string, an integer, or null"
            )

        return cls(
            message,
            error_type,
            code,
            unknown_members(document, _KNOWN_MEMBERS),
        )
