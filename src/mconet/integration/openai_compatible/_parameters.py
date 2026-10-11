"""Generation parameter mapping to OpenAI-compatible request members."""

from __future__ import annotations

from dataclasses import dataclass

from mconet.core.domain import GenerationParameters


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


_NO_PARAMETERS = WireParameters()


def wire_parameters(parameters: GenerationParameters | None) -> WireParameters:
    """Return the request members for validated generation parameters.

    Each value is copied exactly; numbers keep their int or float type and are
    not rounded. ``max_output_tokens`` becomes ``max_tokens``. An empty stop
    tuple means no stop sequences were given, so ``stop`` is omitted rather
    than sent as ``[]``. Stop sequences keep their order and are sent as an
    array even when there is one.

    Domain validation already enforces the ranges every protocol shares. The
    frozen wire profile declares no tighter bound, so service-specific limits,
    such as a maximum temperature or stop count, are left to the service.

    Args:
        parameters: Parameters of the request's GenerationParametersNode, or
            ``None`` when the request has none.

    Returns:
        The members to send. Every member is ``None`` without parameters.
    """
    if parameters is None:
        return _NO_PARAMETERS
    return WireParameters(
        temperature=parameters.temperature,
        top_p=parameters.top_p,
        max_tokens=parameters.max_output_tokens,
        stop=parameters.stop or None,
        seed=parameters.seed,
    )
