"""Semantic validation for protocol-neutral generation parameters."""

from __future__ import annotations

import math
from typing import cast

from mconet.core.domain.generation_parameters import GenerationParameters

_MIN_SAFE_INTEGER = -(2**53 - 1)
_MAX_SAFE_INTEGER = 2**53 - 1


def validate_generation_parameters(
    parameters: GenerationParameters,
) -> GenerationParameters:
    """Validate every present text generation control without normalizing it.

    Protocol-neutral validation establishes finite sampling values, probability
    semantics, JSON-safe integers, positive output limits, and usable stop
    sequences. Provider-specific maxima and unsupported-field policy remain the
    responsibility of the selected protocol adapter and compatibility policy.

    Args:
        parameters: The immutable generation controls to validate.

    Returns:
        The same parameter object after every present field is valid.

    Raises:
        TypeError: If the value or any field has an invalid runtime type.
        ValueError: If a numeric or stop-sequence semantic rule is violated.
    """
    candidate = cast(object, parameters)
    # Require the nominal task configuration so an arbitrary attribute-compatible
    # object cannot bypass the entity's immutable storage contract.
    if not isinstance(candidate, GenerationParameters):
        raise TypeError("parameters must be GenerationParameters.")

    temperature = cast(object, candidate.temperature)
    if temperature is not None:
        # Recheck runtime storage because untyped deserializers can bypass the
        # frozen constructor; bool remains distinct from a JSON number here.
        temperature = _require_number(temperature, "temperature")
        # A negative temperature has no sampling interpretation. No universal
        # upper bound is imposed because target protocols define different ones.
        if temperature < 0:
            raise ValueError("GenerationParameters temperature must be non-negative.")

    top_p = cast(object, candidate.top_p)
    if top_p is not None:
        top_p = _require_number(top_p, "top_p")
        # top_p is a cumulative probability independent of provider-specific
        # mapping, so both inclusive probability boundaries are portable.
        if not 0 <= top_p <= 1:
            raise ValueError(
                "GenerationParameters top_p must be between 0 and 1 inclusive."
            )

    max_output_tokens = cast(object, candidate.max_output_tokens)
    if max_output_tokens is not None:
        max_output_tokens = _require_safe_integer(
            max_output_tokens, "max_output_tokens"
        )
        # Zero cannot request generated output, and negative sentinel values must
        # not silently acquire provider-specific unlimited semantics.
        if max_output_tokens <= 0:
            raise ValueError("GenerationParameters max_output_tokens must be positive.")

    _validate_stop(cast(object, candidate.stop))

    seed = cast(object, candidate.seed)
    if seed is not None:
        # A seed may be negative or zero, but it must round-trip exactly through
        # JSON number implementations used by every supported SDK language.
        _require_safe_integer(seed, "seed")

    return candidate


def _require_number(value: object, field_name: str) -> int | float:
    """Return one exact finite integer or floating-point sampling value."""
    # Exact type membership excludes bool while retaining whole numbers accepted
    # by Python's float-compatible annotation and the language-neutral contract.
    if type(value) not in (int, float):
        raise TypeError(f"GenerationParameters {field_name} must be a number or None.")
    number = cast(int | float, value)
    # math.isfinite accepts both numeric storage types and rejects every NaN or
    # infinity before ordered range comparisons can produce misleading results.
    if not math.isfinite(number):
        raise ValueError(f"GenerationParameters {field_name} must be finite.")
    return number


def _require_safe_integer(value: object, field_name: str) -> int:
    """Return one exact integer in the interoperable JSON safe range."""
    # A nominally frozen object can still be corrupted through low-level dynamic
    # assignment, so type validation precedes all ordered integer comparisons.
    if type(value) is not int:
        raise TypeError(
            f"GenerationParameters {field_name} must be an integer or None."
        )
    integer = value
    # Python integers are unbounded, while JavaScript-based SDK consumers retain
    # exact values only within the shared binary64 safe-integer interval.
    if not _MIN_SAFE_INTEGER <= integer <= _MAX_SAFE_INTEGER:
        raise ValueError(
            f"GenerationParameters {field_name} must be within the "
            "interoperable safe integer range."
        )
    return integer


def _validate_stop(value: object) -> None:
    """Require ordered immutable stop storage containing non-empty strings."""
    # Tuple storage guarantees stable membership and order throughout task
    # planning; accepting a list here would undo the entity's immutability rule.
    if not isinstance(value, tuple):
        raise TypeError("GenerationParameters stop must be a tuple.")
    for index, sequence in enumerate(cast(tuple[object, ...], value)):
        # Report member type before content so corrupted values never participate
        # in text operations or appear as implicit protocol strings.
        if not isinstance(sequence, str):
            raise TypeError("GenerationParameters stop must contain only strings.")
        # Whitespace is a meaningful stop sequence and remains valid; only the
        # zero-length string would match without consuming generated text.
        if not sequence:
            raise ValueError(
                f"GenerationParameters stop sequence at index {index} "
                "must not be empty."
            )
