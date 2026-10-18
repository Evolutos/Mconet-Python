"""Generation parameter mapping to OpenAI-compatible request members."""

from __future__ import annotations

from dataclasses import dataclass

from mconet.core.domain import (
    ErrorCategory,
    GenerationParameters,
    InteractionPhase,
    JsonValue,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.integration.openai_compatible._tool_calls import (
    tool_choice_json,
    tool_definition_json,
)

UNSUPPORTED_GENERATION_PARAMETER_CODE = "unsupported_generation_parameter"
"""Stable code for a parameter value outside the frozen wire profile."""

MAX_TEMPERATURE = 2
"""Largest ``temperature`` the wire profile defines."""

_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_PROTOCOL_ADAPTATION = InteractionPhase(OpenIdentifier("protocol_adaptation"))


@dataclass(frozen=True, slots=True)
class WireParameters:
    """Hold the optional sampling members of one request body.

    ``None`` omits the member so the service default applies.
    """

    temperature: float | None = None
    """``temperature`` member value."""

    top_p: float | None = None
    """``top_p`` member value."""

    max_tokens: int | None = None
    """``max_tokens`` member value."""

    stop: tuple[str, ...] | None = None
    """``stop`` member value, always sent as an array when present."""

    seed: int | None = None
    """``seed`` member value."""

    tools: tuple[dict[str, JsonValue], ...] | None = None
    """``tools`` member value, or ``None`` to omit it."""

    tool_choice: JsonValue | None = None
    """``tool_choice`` member value, or ``None`` to omit it."""


_NO_PARAMETERS = WireParameters()


def wire_parameters(
    parameters: GenerationParameters | None, *, enforce_profile: bool
) -> WireParameters:
    """Return the request members for validated generation parameters.

    Each value is copied exactly; numbers keep their int or float type and are
    not rounded. ``max_output_tokens`` becomes ``max_tokens``. An empty stop
    tuple means no stop sequences were given, so ``stop`` is omitted rather
    than sent as ``[]``. Stop sequences keep their order and are sent as an
    array even when there is one.

    Domain validation already bounds ``top_p`` to ``[0, 1]``, requires a
    non-negative ``temperature`` and a positive ``max_output_tokens``, and
    keeps ``seed`` a safe integer. The profile adds only the ``temperature``
    maximum of 2, enforced when the policy requires the profile; a relaxed
    policy sends a larger value unchanged and leaves acceptance to the service.
    ``seed`` is part of the profile, so it is sent in every mode. Limits the
    profile does not declare, such as a stop count, are left to the service.

    Args:
        parameters: Parameters of the request's GenerationParametersNode, or
            ``None`` when the request has none.
        enforce_profile: Whether values outside the wire profile fail.

    Returns:
        The members to send. Every member is ``None`` without parameters.

    Raises:
        ModelInteractionError: If the profile is enforced and ``temperature``
            exceeds its maximum.
    """
    if parameters is None:
        return _NO_PARAMETERS
    temperature = parameters.temperature
    if enforce_profile and temperature is not None and temperature > MAX_TEMPERATURE:
        # The value is caller request data, so naming the bound, not the value,
        # is enough to correct it without echoing request content.
        raise ModelInteractionError(
            category=_UNSUPPORTED_FEATURE,
            phase=_PROTOCOL_ADAPTATION,
            code=UNSUPPORTED_GENERATION_PARAMETER_CODE,
            message=(
                "Generation parameter temperature exceeds the OpenAI-compatible "
                f"chat completions maximum of {MAX_TEMPERATURE}."
            ),
        )
    return WireParameters(
        temperature=temperature,
        top_p=parameters.top_p,
        max_tokens=parameters.max_output_tokens,
        stop=parameters.stop or None,
        seed=parameters.seed,
        tools=_tools(parameters),
        tool_choice=_tool_choice(parameters),
    )


def _tools(parameters: GenerationParameters) -> tuple[dict[str, JsonValue], ...] | None:
    """Return the tools array, or ``None`` when the request declares none.

    Args:
        parameters: Generation controls for the request being encoded.

    Returns:
        One JSON object per declared function tool, in declaration order.
    """
    # An empty tuple means the caller did not offer tools. Omitting the member
    # leaves the service default, which is no tools, without sending ``[]``.
    if not parameters.tools:
        return None
    return tuple(tool_definition_json(tool) for tool in parameters.tools)


def _tool_choice(parameters: GenerationParameters) -> JsonValue | None:
    """Return the tool_choice member, or ``None`` when it was not set.

    Args:
        parameters: Generation controls for the request being encoded.

    Returns:
        ``None`` when the caller omitted the control, otherwise the mode
        string or the named-function object.
    """
    # None omits the member so the service default applies. It is not encoded
    # as JSON null.
    if parameters.tool_choice is None:
        return None
    # A choice names a tool or a mode over the declared tools. Sending it
    # alone would ask the service to select from a list that is not present.
    if not parameters.tools:
        raise ValueError("GenerationParameters tool_choice requires a declared tool.")
    return tool_choice_json(parameters.tool_choice)
