"""Immutable protocol-neutral text generation parameter values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class GenerationParameters:
    """Carry optional model generation controls as task configuration.

    Every field is independently optional so a task can express only the
    controls selected by its caller. The values remain protocol-neutral: a
    later adapter decides how supported fields map to a target request under
    the active compatibility policy. Message documents never own these values.

    Construction enforces immutable storage shape only. Numeric ranges,
    finiteness, portable integer bounds, and stop-sequence content belong to
    the dedicated generation-parameter validator.
    """

    temperature: float | None = None
    """Optional sampling temperature retained without range normalization."""

    top_p: float | None = None
    """Optional nucleus-sampling probability retained independently."""

    max_output_tokens: int | None = None
    """Optional maximum number of tokens requested for generated output."""

    stop: tuple[str, ...] = ()
    """Ordered immutable stop sequences; an empty tuple requests no stops."""

    seed: int | None = None
    """Optional deterministic sampling seed when supported by the target."""

    def __post_init__(self) -> None:
        """Require exact optional number types and immutable stop storage."""
        # Integers are valid real-number inputs for sampling controls in Python,
        # but bool must not enter as its 0/1 integer subclass. Range and finite
        # checks are deliberately deferred to the field-specific validator.
        for field_name, value in (
            ("temperature", cast(object, self.temperature)),
            ("top_p", cast(object, self.top_p)),
        ):
            if value is not None and type(value) not in (int, float):
                raise TypeError(
                    f"GenerationParameters {field_name} must be a number or None."
                )

        # Token counts and seeds must use exact integer storage. Zero, negative,
        # and non-portable integers remain representable until semantic validation
        # can return a stable diagnostic for the specific field.
        for field_name, value in (
            ("max_output_tokens", cast(object, self.max_output_tokens)),
            ("seed", cast(object, self.seed)),
        ):
            if value is not None and type(value) is not int:
                raise TypeError(
                    f"GenerationParameters {field_name} must be an integer or None."
                )

        stop = cast(object, self.stop)
        # Tuple storage preserves caller order and prevents later insertion or
        # removal while a protocol adapter is preparing the same task request.
        if not isinstance(stop, tuple):
            raise TypeError("GenerationParameters stop must be a tuple.")
        for sequence in cast(tuple[object, ...], stop):
            # Empty text, duplicates, length, and provider limits are semantic
            # rules; construction only prevents non-text values from entering.
            if not isinstance(sequence, str):
                raise TypeError("GenerationParameters stop must contain only strings.")
