"""Semantic validation for protocol-neutral generation parameters."""

from __future__ import annotations

import math
from typing import cast

from mconet.core.domain.function_tool import FunctionTool, function_tool_parameters_json
from mconet.core.domain.generation_parameters import GenerationParameters
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers

_STANDARD_TOOL_CHOICES = frozenset(("auto", "none", "required"))

_MIN_SAFE_INTEGER = -(2**53 - 1)
_MAX_SAFE_INTEGER = 2**53 - 1


def validate_generation_parameters(
    parameters: GenerationParameters,
) -> GenerationParameters:
    """Validate every present text generation control without normalizing it.

    Protocol-neutral validation establishes finite sampling values, probability
    semantics, JSON-safe integers, positive output limits, usable stop
    sequences, distinct tool names, and a tool choice that names a declared
    tool. Provider-specific maxima and unsupported-field policy remain the
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

    _validate_tools(cast(object, candidate.tools), candidate.tool_choice)
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


def _validate_tools(value: object, tool_choice: object) -> None:
    """Require distinct function tools and a choice that names one of them.

    Args:
        value: The ``tools`` tuple stored on the generation parameters.
        tool_choice: The ``tool_choice`` string, or ``None`` when omitted.

    Raises:
        TypeError: If a tool or the choice has an invalid runtime type.
        ValueError: If a name is blank or duplicated, a schema number is not
            portable, or the choice does not name a declared tool.
    """
    # Tuple storage keeps declaration order. A list would let a caller change
    # the tools after validation and before the adapter encodes them.
    if not isinstance(value, tuple):
        raise TypeError("GenerationParameters tools must be a tuple.")
    names: set[str] = set()
    for tool in cast(tuple[object, ...], value):
        # Recheck the element type because a low-level assignment can bypass
        # the frozen constructor that first required FunctionTool values.
        if not isinstance(tool, FunctionTool):
            raise TypeError(
                "GenerationParameters tools must contain FunctionTool values."
            )
        name = tool.name
        # A blank name cannot be cited by a tool call or by tool_choice.
        if not name or name.isspace():
            raise ValueError("FunctionTool name must not be empty or whitespace.")
        # Two tools with one name would make a named tool_choice ambiguous.
        if name in names:
            raise ValueError("GenerationParameters tools must use distinct names.")
        names.add(name)
        # The stored schema is read-only. The thawed copy is the JSON object
        # the number walk accepts, and editing it cannot change the tool.
        parameters = function_tool_parameters_json(tool)
        if parameters is not None:
            if not isinstance(parameters, dict):
                raise TypeError(
                    "FunctionTool parameters must be a JSON object or None."
                )
            # Schema numbers must round-trip through every supported SDK
            # language before the adapter copies them onto the request.
            validate_json_value_numbers(cast(JsonValue, parameters))

    if tool_choice is None:
        # Omitting the choice leaves the service default. It does not require
        # the request to declare any tools.
        return
    if not isinstance(tool_choice, str):
        raise TypeError("GenerationParameters tool_choice must be a string or None.")
    # A blank choice cannot select a mode or a function.
    if not tool_choice or tool_choice.isspace():
        raise ValueError(
            "GenerationParameters tool_choice must not be empty or whitespace."
        )
    # A choice without a declared tool has nothing to select. Modes included:
    # auto, none, and required are not meaningful until a tool exists.
    if not names:
        raise ValueError("GenerationParameters tool_choice requires a declared tool.")
    # auto, none, and required are modes. Every other string selects one tool
    # by the exact name declared above.
    if tool_choice not in _STANDARD_TOOL_CHOICES and tool_choice not in names:
        raise ValueError(
            "GenerationParameters tool_choice must be auto, none, required, "
            "or the name of a declared tool."
        )
