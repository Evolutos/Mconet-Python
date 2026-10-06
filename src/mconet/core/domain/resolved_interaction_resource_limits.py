"""Complete byte resource limits produced by configuration resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class ResolvedInteractionResourceLimits:
    """Carry one finite integer value for every interaction byte limit.

    Resolution must supply all three fields, so this value object has no
    optional members or unbounded sentinel. Positivity and signed 64-bit range
    checks belong to the dedicated resource-limit validator.
    """

    max_response_body_bytes: int
    """Maximum number of bytes accepted for a unary response body."""

    max_streaming_error_body_bytes: int
    """Maximum bytes collected from an initial streaming error body."""

    max_frame_bytes: int
    """Maximum encoded size of one framed streaming event."""

    def __post_init__(self) -> None:
        """Require every resolved field to use finite integer storage."""
        # Check the complete field set independently so dynamically typed callers
        # cannot introduce None or a non-integer unbounded sentinel after static
        # type checking. Semantic integer validation remains a separate concern.
        for field_name, value in (
            ("max_response_body_bytes", cast(object, self.max_response_body_bytes)),
            (
                "max_streaming_error_body_bytes",
                cast(object, self.max_streaming_error_body_bytes),
            ),
            ("max_frame_bytes", cast(object, self.max_frame_bytes)),
        ):
            # Exact type membership excludes bool as well as floating-point
            # infinity and NaN; Python integers themselves are always finite.
            if type(value) is not int:
                raise TypeError(
                    f"ResolvedInteractionResourceLimits {field_name} must be "
                    "an integer."
                )
