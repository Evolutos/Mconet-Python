"""Value and boundary tests for immutable GenerationParameters."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from math import inf, nan
from typing import cast

from mconet.core.domain import GenerationParameters


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected domain storage diagnostic."""
    # Check the message as well as the exception class so an unrelated runtime
    # failure cannot accidentally satisfy a negative constructor test.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_generation_parameters_allow_every_control_to_be_omitted() -> None:
    """Verify an empty task configuration does not invent model controls."""
    parameters = GenerationParameters()

    # None represents an omitted scalar control, while the immutable empty tuple
    # is the canonical no-stop value used by later mapping code.
    assert parameters.temperature is None
    assert parameters.top_p is None
    assert parameters.max_output_tokens is None
    assert parameters.stop == ()
    assert parameters.seed is None


def test_generation_parameters_preserve_complete_caller_input() -> None:
    """Verify all standard fields retain exact independent caller values."""
    parameters = GenerationParameters(
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=512,
        stop=("END", "\nUser:"),
        seed=42,
    )

    # No field is inferred from another and stop order remains significant for
    # deterministic cross-platform task serialization.
    assert parameters.temperature == 0.7
    assert parameters.top_p == 0.95
    assert parameters.max_output_tokens == 512
    assert parameters.stop == ("END", "\nUser:")
    assert parameters.seed == 42


def test_generation_parameters_accept_integer_sampling_numbers() -> None:
    """Verify whole JSON numbers remain valid sampling-control storage."""
    parameters = GenerationParameters(temperature=1, top_p=1)

    # Python accepts integers where a float annotation is expected; retaining the
    # exact values avoids constructor normalization before semantic validation.
    assert parameters.temperature == 1
    assert parameters.top_p == 1


def test_generation_parameters_defer_semantic_number_rules() -> None:
    """Verify the later validator can observe every invalid numeric boundary."""
    parameters = GenerationParameters(
        temperature=nan,
        top_p=inf,
        max_output_tokens=0,
        stop=("", "duplicate", "duplicate"),
        seed=1 << 80,
    )

    # Construction enforces representation only. Finiteness, ranges, positivity,
    # portable seed bounds, and stop content require field-specific validation.
    assert parameters.temperature is not None
    assert parameters.temperature != parameters.temperature
    assert parameters.top_p == inf
    assert parameters.max_output_tokens == 0
    assert parameters.stop == ("", "duplicate", "duplicate")
    assert parameters.seed == 1 << 80


def test_generation_parameters_have_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability cover every control field."""
    first = GenerationParameters(0.5, 0.9, 128, ("done",), 7)
    same = GenerationParameters(0.5, 0.9, 128, ("done",), 7)
    different = GenerationParameters(0.5, 0.9, 128, (), 7)

    # Frozen record and tuple storage make one configuration safe to share across
    # planning and mapping without a caller changing values between those steps.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("seed", 8),
        "cannot assign to field",
    )


def test_generation_parameters_reject_non_number_sampling_storage() -> None:
    """Verify sampling controls reject booleans, strings, and other objects."""
    invalid_parameters = (
        lambda: GenerationParameters(temperature=cast(float, True)),
        lambda: GenerationParameters(top_p=cast(float, "0.9")),
        lambda: GenerationParameters(temperature=cast(float, object())),
    )

    # Every invalid shape fails during construction so adapters never receive a
    # logical flag or coercible text masquerading as a sampling number.
    for create_parameters in invalid_parameters:
        _assert_raises(TypeError, create_parameters, "must be a number or None")


def test_generation_parameters_reject_non_integer_count_and_seed_storage() -> None:
    """Verify token counts and seeds require exact non-boolean integers."""
    invalid_parameters = (
        lambda: GenerationParameters(max_output_tokens=cast(int, 32.0)),
        lambda: GenerationParameters(max_output_tokens=cast(int, True)),
        lambda: GenerationParameters(seed=cast(int, "42")),
    )

    # Counts and seeds cannot rely on lossy or truth-value coercion; their range
    # remains a separate semantic concern once exact integer storage is known.
    for create_parameters in invalid_parameters:
        _assert_raises(TypeError, create_parameters, "must be an integer or None")


def test_generation_parameters_require_immutable_text_stop_storage() -> None:
    """Verify stop sequences use a tuple containing text values only."""
    invalid_parameters = (
        lambda: GenerationParameters(stop=cast(tuple[str, ...], ["done"])),
        lambda: GenerationParameters(stop=cast(tuple[str, ...], ("done", 1))),
    )

    # Reject a mutable container and invalid members independently; this keeps
    # adapter iteration stable while leaving content policy to the validator.
    _assert_raises(TypeError, invalid_parameters[0], "stop must be a tuple")
    _assert_raises(TypeError, invalid_parameters[1], "only strings")
