"""Optional per-interaction byte resource limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class InteractionResourceLimits:
    """Carry optional byte limits before configuration resolution.

    Every field may be omitted independently so interaction values can override
    only selected client defaults. Positivity, signed 64-bit portability, and
    fallback defaults belong to later validation and resolution steps.
    """

    max_response_body_bytes: int | None = None
    """Optional maximum number of bytes accepted for a unary response body."""

    max_streaming_error_body_bytes: int | None = None
    """Optional maximum bytes collected from an initial streaming error body."""

    max_frame_bytes: int | None = None
    """Optional maximum encoded size of one framed streaming event."""

    def __post_init__(self) -> None:
        """Require each supplied limit to use exact integer storage."""
        # Validate fields independently so zero, negative, and out-of-range
        # integers remain representable for the dedicated semantic validator to
        # reject with stable field-specific diagnostics in its own work step.
        for field_name, value in (
            ("max_response_body_bytes", cast(object, self.max_response_body_bytes)),
            (
                "max_streaming_error_body_bytes",
                cast(object, self.max_streaming_error_body_bytes),
            ),
            ("max_frame_bytes", cast(object, self.max_frame_bytes)),
        ):
            # Exact type membership rejects bool, which Python otherwise treats
            # as an int and could silently turn a configuration flag into 0/1.
            if value is not None and type(value) is not int:
                raise TypeError(
                    f"InteractionResourceLimits {field_name} must be an integer "
                    "or None."
                )
