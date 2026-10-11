"""Tests for the OpenAI-compatible token usage wire value."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import JsonValue, ModelInteractionError
from mconet.integration.openai_compatible import OpenAIChatCompletionUsageDTO


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _failure_message(value: JsonValue) -> str:
    """Return the protocol failure message for one decoded usage object."""
    error = _capture(lambda: OpenAIChatCompletionUsageDTO.from_json(value, "/usage"))
    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_protocol_response"
    return error.message


def test_usage_reads_all_counts_and_captures_breakdowns() -> None:
    """Verify counts map and nested breakdowns stay in extensions."""
    decoded: JsonValue = {
        "prompt_tokens": 37,
        "completion_tokens": 12,
        "total_tokens": 49,
        "prompt_tokens_details": {"cached_tokens": 8},
    }

    usage = OpenAIChatCompletionUsageDTO.from_json(decoded, "/usage")

    assert usage.prompt_tokens == 37
    assert usage.completion_tokens == 12
    assert usage.total_tokens == 49
    assert dict(usage.extensions) == {"prompt_tokens_details": {"cached_tokens": 8}}


def test_usage_absent_counts_are_none_and_zero_is_kept() -> None:
    """Verify absence and an explicit zero stay distinguishable."""
    usage = OpenAIChatCompletionUsageDTO.from_json({"completion_tokens": 0})

    assert usage.prompt_tokens is None
    assert usage.completion_tokens == 0
    assert usage.total_tokens is None


def test_usage_total_is_reported_rather_than_computed() -> None:
    """Verify a total that differs from the sum is preserved."""
    usage = OpenAIChatCompletionUsageDTO.from_json(
        {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 10}
    )

    assert usage.total_tokens == 10


def test_usage_rejects_null_negative_boolean_and_fractional_counts() -> None:
    """Verify a present count must be a non-negative integer."""
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        for value in (None, -1, True, 1.5, "1"):
            message = _failure_message({name: value})
            assert message == (
                f"OpenAI-compatible response field /usage/{name} "
                "must be a non-negative integer."
            )


def test_usage_rejects_a_non_object() -> None:
    """Verify usage must be an object when it is read."""
    assert _failure_message(7) == (
        "OpenAI-compatible response field /usage must be an object."
    )


def test_usage_construction_requires_optional_non_negative_integers() -> None:
    """Verify direct construction applies the same count rules."""
    bool_error = _capture(
        lambda: OpenAIChatCompletionUsageDTO(prompt_tokens=cast(int, False))
    )
    negative_error = _capture(lambda: OpenAIChatCompletionUsageDTO(total_tokens=-2))

    assert isinstance(bool_error, TypeError)
    assert str(bool_error) == (
        "OpenAIChatCompletionUsageDTO prompt_tokens must be an integer or None."
    )
    assert isinstance(negative_error, ValueError)
    assert str(negative_error) == (
        "OpenAIChatCompletionUsageDTO total_tokens must not be negative."
    )


def test_usage_is_frozen() -> None:
    """Verify decoded usage cannot be changed by later consumers."""
    usage = OpenAIChatCompletionUsageDTO(1, 2, 3)

    error = _capture(lambda: setattr(usage, "total_tokens", 4))

    assert isinstance(error, FrozenInstanceError)
