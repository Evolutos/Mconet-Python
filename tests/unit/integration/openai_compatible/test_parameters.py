"""Tests for mapping generation parameters to request members."""

from mconet.core.domain import GenerationParameters
from mconet.integration.openai_compatible._parameters import (
    WireParameters,
    wire_parameters,
)


def test_no_parameters_omit_every_member() -> None:
    """Verify absent parameters and default parameters send nothing."""
    assert wire_parameters(None) == WireParameters()
    assert wire_parameters(GenerationParameters()) == WireParameters()


def test_each_parameter_maps_to_its_member_exactly() -> None:
    """Verify temperature, top_p, max_tokens, stop, and seed are copied."""
    parameters = GenerationParameters(
        temperature=0.25,
        top_p=0.9,
        max_output_tokens=512,
        stop=("<END>", "\u505c\u6b62", "\U0001f6d1"),
        seed=-42,
    )

    assert wire_parameters(parameters) == WireParameters(
        temperature=0.25,
        top_p=0.9,
        max_tokens=512,
        stop=("<END>", "\u505c\u6b62", "\U0001f6d1"),
        seed=-42,
    )


def test_parameters_are_independent() -> None:
    """Verify one set parameter does not cause another to be sent."""
    assert wire_parameters(GenerationParameters(temperature=0.0)) == WireParameters(
        temperature=0.0
    )
    assert wire_parameters(GenerationParameters(top_p=1)) == WireParameters(top_p=1)
    assert wire_parameters(GenerationParameters(max_output_tokens=1)) == (
        WireParameters(max_tokens=1)
    )
    assert wire_parameters(GenerationParameters(seed=0)) == WireParameters(seed=0)


def test_integral_numbers_keep_their_type() -> None:
    """Verify an int temperature is not turned into a float."""
    members = wire_parameters(GenerationParameters(temperature=1, top_p=0))

    assert type(members.temperature) is int
    assert type(members.top_p) is int


def test_a_single_stop_sequence_stays_an_array() -> None:
    """Verify stop is always an ordered tuple, never a bare string."""
    assert wire_parameters(GenerationParameters(stop=(" ",))).stop == (" ",)
