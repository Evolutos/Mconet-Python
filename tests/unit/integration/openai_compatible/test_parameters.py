"""Tests for mapping generation parameters to request members."""

from collections.abc import Callable

from mconet.core.domain import GenerationParameters, ModelInteractionError
from mconet.integration.openai_compatible._parameters import (
    MAX_TEMPERATURE,
    UNSUPPORTED_GENERATION_PARAMETER_CODE,
    WireParameters,
    wire_parameters,
)

_BOTH_MODES = (True, False)
_MAX_SAFE_INTEGER = 2**53 - 1


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def test_no_parameters_omit_every_member() -> None:
    """Verify absent parameters and default parameters send nothing."""
    for enforce in _BOTH_MODES:
        assert wire_parameters(None, enforce_profile=enforce) == WireParameters()
        assert wire_parameters(GenerationParameters(), enforce_profile=enforce) == (
            WireParameters()
        )


def test_each_parameter_maps_to_its_member_exactly() -> None:
    """Verify temperature, top_p, max_tokens, stop, and seed are copied."""
    parameters = GenerationParameters(
        temperature=0.25,
        top_p=0.9,
        max_output_tokens=512,
        stop=("<END>", "\u505c\u6b62", "\U0001f6d1"),
        seed=-42,
    )

    for enforce in _BOTH_MODES:
        assert wire_parameters(parameters, enforce_profile=enforce) == WireParameters(
            temperature=0.25,
            top_p=0.9,
            max_tokens=512,
            stop=("<END>", "\u505c\u6b62", "\U0001f6d1"),
            seed=-42,
        )


def test_parameters_are_independent() -> None:
    """Verify one set parameter does not cause another to be sent."""
    cases: tuple[tuple[GenerationParameters, WireParameters], ...] = (
        (GenerationParameters(temperature=0.0), WireParameters(temperature=0.0)),
        (GenerationParameters(top_p=1), WireParameters(top_p=1)),
        (GenerationParameters(max_output_tokens=1), WireParameters(max_tokens=1)),
        (GenerationParameters(seed=0), WireParameters(seed=0)),
    )
    for enforce in _BOTH_MODES:
        for parameters, members in cases:
            assert wire_parameters(parameters, enforce_profile=enforce) == members


def test_integral_numbers_keep_their_type() -> None:
    """Verify an int temperature is not turned into a float."""
    members = wire_parameters(
        GenerationParameters(temperature=1, top_p=0), enforce_profile=True
    )

    assert type(members.temperature) is int
    assert type(members.top_p) is int


def test_temperature_maximum_is_inclusive_in_every_mode() -> None:
    """Verify the profile maximum itself is accepted under any policy."""
    for enforce in _BOTH_MODES:
        for value in (0, 2, 2.0):
            members = wire_parameters(
                GenerationParameters(temperature=value), enforce_profile=enforce
            )

            assert members.temperature == value
    assert MAX_TEMPERATURE == 2


def test_strict_profile_rejects_a_temperature_above_the_maximum() -> None:
    """Verify an enforced profile fails without echoing the request value."""
    for value in (2.0000001, 3, 1e9):
        error = _capture(
            lambda value=value: wire_parameters(
                GenerationParameters(temperature=value), enforce_profile=True
            )
        )

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "unsupported_feature"
        assert error.phase.id.value == "protocol_adaptation"
        assert error.code == UNSUPPORTED_GENERATION_PARAMETER_CODE
        assert error.message == (
            "Generation parameter temperature exceeds the OpenAI-compatible "
            "chat completions maximum of 2."
        )


def test_relaxed_profile_sends_a_temperature_above_the_maximum() -> None:
    """Verify a relaxed policy keeps the original value for the service."""
    members = wire_parameters(
        GenerationParameters(temperature=3.5), enforce_profile=False
    )

    assert members == WireParameters(temperature=3.5)


def test_top_p_domain_range_is_sent_unchanged_in_every_mode() -> None:
    """Verify the profile adds no top_p bound beyond the domain range."""
    for enforce in _BOTH_MODES:
        for value in (0, 0.5, 1.0):
            members = wire_parameters(
                GenerationParameters(top_p=value), enforce_profile=enforce
            )

            assert members == WireParameters(top_p=value)


def test_max_tokens_boundaries_use_the_protocol_member_name() -> None:
    """Verify the smallest and largest portable counts become max_tokens."""
    for enforce in _BOTH_MODES:
        for value in (1, _MAX_SAFE_INTEGER):
            members = wire_parameters(
                GenerationParameters(max_output_tokens=value),
                enforce_profile=enforce,
            )

            assert members == WireParameters(max_tokens=value)


def test_stop_sequences_cover_empty_single_and_many() -> None:
    """Verify empty stop is omitted and stop otherwise stays an ordered array."""
    cases: tuple[tuple[tuple[str, ...], tuple[str, ...] | None], ...] = (
        ((), None),
        ((" ",), (" ",)),
        (("b", "a", "b"), ("b", "a", "b")),
    )
    for enforce in _BOTH_MODES:
        for stop, expected in cases:
            members = wire_parameters(
                GenerationParameters(stop=stop), enforce_profile=enforce
            )

            assert members.stop == expected


def test_seed_is_supported_and_sent_in_every_mode() -> None:
    """Verify seed is never treated as unsupported, including its bounds."""
    for enforce in _BOTH_MODES:
        for value in (-_MAX_SAFE_INTEGER, 0, _MAX_SAFE_INTEGER):
            members = wire_parameters(
                GenerationParameters(seed=value), enforce_profile=enforce
            )

            assert members == WireParameters(seed=value)
