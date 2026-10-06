"""Field-level semantic tests for GenerationParameters validation."""

from collections.abc import Callable
from math import inf, nan
from typing import cast

from mconet.core.domain import (
    GenerationParameters,
    validate_generation_parameters,
)

_MIN_SAFE_INTEGER = -(2**53 - 1)
_MAX_SAFE_INTEGER = 2**53 - 1


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require one validation action to raise the expected field diagnostic."""
    # Match the message so a failure from an earlier unrelated field cannot make
    # a later-field boundary test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _replace_field(
    parameters: GenerationParameters,
    field_name: str,
    value: object,
) -> GenerationParameters:
    """Simulate an untyped deserializer bypassing frozen constructor checks."""
    # object.__setattr__ deliberately creates a corrupted runtime object so the
    # public validator's defensive type checks are exercised directly.
    object.__setattr__(parameters, field_name, value)
    return parameters


def test_generation_parameters_validator_preserves_valid_identity() -> None:
    """Verify complete valid controls return unchanged and unnormalized."""
    parameters = GenerationParameters(
        temperature=1,
        top_p=0.9,
        max_output_tokens=512,
        stop=(" ", "完成"),
        seed=-42,
    )

    # Whole-number temperature, whitespace, Unicode, and a negative seed are all
    # protocol-neutral values and retain exact representation and object identity.
    assert validate_generation_parameters(parameters) is parameters
    assert parameters.temperature == 1
    assert parameters.stop == (" ", "完成")
    assert parameters.seed == -42


def test_generation_parameters_validator_accepts_omitted_and_boundary_values() -> None:
    """Verify optional absence and every inclusive portable boundary succeeds."""
    empty = GenerationParameters()
    lower = GenerationParameters(
        temperature=0,
        top_p=0,
        max_output_tokens=1,
        seed=_MIN_SAFE_INTEGER,
    )
    upper = GenerationParameters(
        temperature=1e308,
        top_p=1,
        max_output_tokens=_MAX_SAFE_INTEGER,
        seed=_MAX_SAFE_INTEGER,
    )

    # Core applies no provider temperature ceiling, while probabilities and JSON
    # integers retain their inclusive cross-platform boundaries.
    assert validate_generation_parameters(empty) is empty
    assert validate_generation_parameters(lower) is lower
    assert validate_generation_parameters(upper) is upper


def test_generation_parameters_validator_rejects_wrong_nominal_value() -> None:
    """Verify an attribute-compatible or unrelated object is not accepted."""
    _assert_raises(
        TypeError,
        lambda: validate_generation_parameters(cast(GenerationParameters, object())),
        "parameters must be GenerationParameters",
    )


def test_generation_parameters_validator_rechecks_sampling_types() -> None:
    """Verify bypassed temperature and top_p storage cannot evade type rules."""
    invalid_parameters = (
        (_replace_field(GenerationParameters(), "temperature", True), "temperature"),
        (_replace_field(GenerationParameters(), "top_p", "0.5"), "top_p"),
    )

    # Constructor checks are not trusted at the validation boundary because
    # dynamic decoders can materialize or mutate objects outside typed code.
    for parameters, field_name in invalid_parameters:
        _assert_raises(
            TypeError,
            lambda parameters=parameters: validate_generation_parameters(parameters),
            f"{field_name} must be a number or None",
        )


def test_generation_parameters_validator_rejects_nonfinite_sampling_values() -> None:
    """Verify NaN and both infinities fail before numeric range comparisons."""
    invalid_parameters = (
        (GenerationParameters(temperature=nan), "temperature"),
        (GenerationParameters(top_p=inf), "top_p"),
        (GenerationParameters(temperature=-inf), "temperature"),
    )

    # Each IEEE special value is unsuitable for JSON and must produce the finite
    # diagnostic rather than falling through to a misleading range error.
    for parameters, field_name in invalid_parameters:
        _assert_raises(
            ValueError,
            lambda parameters=parameters: validate_generation_parameters(parameters),
            f"{field_name} must be finite",
        )


def test_generation_parameters_validator_rejects_negative_temperature() -> None:
    """Verify temperature has a portable lower bound but no Core upper bound."""
    _assert_raises(
        ValueError,
        lambda: validate_generation_parameters(
            GenerationParameters(temperature=-0.001)
        ),
        "temperature must be non-negative",
    )


def test_generation_parameters_validator_rejects_top_p_outside_probability() -> None:
    """Verify nucleus probability rejects values below zero and above one."""
    for top_p in (-0.001, 1.001):
        # Both sides of the inclusive interval are tested independently so a
        # one-sided comparison cannot accidentally satisfy the contract.
        _assert_raises(
            ValueError,
            lambda top_p=top_p: validate_generation_parameters(
                GenerationParameters(top_p=top_p)
            ),
            "top_p must be between 0 and 1 inclusive",
        )


def test_generation_parameters_validator_rechecks_integer_types() -> None:
    """Verify bypassed max-token and seed storage require exact integers."""
    invalid_parameters = (
        (
            _replace_field(GenerationParameters(), "max_output_tokens", 1.0),
            "max_output_tokens",
        ),
        (_replace_field(GenerationParameters(), "seed", True), "seed"),
    )

    # Exact checks reject float and bool before ordered safe-integer comparisons.
    for parameters, field_name in invalid_parameters:
        _assert_raises(
            TypeError,
            lambda parameters=parameters: validate_generation_parameters(parameters),
            f"{field_name} must be an integer or None",
        )


def test_generation_parameters_validator_rejects_unsafe_integers() -> None:
    """Verify both integer fields enforce both JSON safe-range boundaries."""
    invalid_parameters = (
        (
            GenerationParameters(max_output_tokens=_MAX_SAFE_INTEGER + 1),
            "max_output_tokens",
        ),
        (
            GenerationParameters(max_output_tokens=_MIN_SAFE_INTEGER - 1),
            "max_output_tokens",
        ),
        (GenerationParameters(seed=_MAX_SAFE_INTEGER + 1), "seed"),
        (GenerationParameters(seed=_MIN_SAFE_INTEGER - 1), "seed"),
    )

    # Range validation precedes positivity, preserving an overflow diagnostic for
    # a negative value that is also not a valid positive output-token count.
    for parameters, field_name in invalid_parameters:
        _assert_raises(
            ValueError,
            lambda parameters=parameters: validate_generation_parameters(parameters),
            f"{field_name} must be within the interoperable safe integer range",
        )


def test_generation_parameters_validator_rejects_nonpositive_output_tokens() -> None:
    """Verify zero and ordinary negative token counts cannot imply unlimited."""
    for max_output_tokens in (0, -1):
        _assert_raises(
            ValueError,
            lambda max_output_tokens=max_output_tokens: validate_generation_parameters(
                GenerationParameters(max_output_tokens=max_output_tokens)
            ),
            "max_output_tokens must be positive",
        )


def test_generation_parameters_validator_rechecks_stop_storage() -> None:
    """Verify a bypassed mutable container or non-text member fails stably."""
    mutable = _replace_field(GenerationParameters(), "stop", ["done"])
    invalid_member = _replace_field(GenerationParameters(), "stop", ("done", 1))

    # Container and member failures remain distinct so decoder bugs are reported
    # at the exact contract boundary they violate.
    _assert_raises(
        TypeError,
        lambda: validate_generation_parameters(mutable),
        "stop must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: validate_generation_parameters(invalid_member),
        "stop must contain only strings",
    )


def test_generation_parameters_validator_rejects_empty_stop_with_index() -> None:
    """Verify an empty sequence identifies its exact ordered tuple position."""
    parameters = GenerationParameters(stop=("done", "", "later"))

    # Index reporting disambiguates repeated or multiple invalid values without
    # trimming whitespace or changing any valid neighboring sequence.
    _assert_raises(
        ValueError,
        lambda: validate_generation_parameters(parameters),
        "stop sequence at index 1 must not be empty",
    )
