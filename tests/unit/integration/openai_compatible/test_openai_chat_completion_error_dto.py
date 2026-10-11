"""Tests for the OpenAI-compatible failure body wire values."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import JsonValue, ModelInteractionError
from mconet.integration.openai_compatible import (
    OpenAIChatCompletionErrorDTO,
    OpenAIChatCompletionErrorResponseDTO,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _failure_message(value: JsonValue) -> str:
    """Return the protocol failure message for one decoded failure body."""
    error = _capture(lambda: OpenAIChatCompletionErrorResponseDTO.from_json(value))
    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_protocol_response"
    return error.message


def test_failure_body_reads_error_members_and_captures_the_rest() -> None:
    """Verify message, type, and code map and extras are captured per level."""
    decoded: JsonValue = {
        "error": {
            "message": "Rate limit reached.",
            "type": "requests",
            "code": "rate_limit_exceeded",
            "param": None,
        },
        "request": "trace-1",
    }

    body = OpenAIChatCompletionErrorResponseDTO.from_json(decoded)

    assert body.error.message == "Rate limit reached."
    assert body.error.type == "requests"
    assert body.error.code == "rate_limit_exceeded"
    assert dict(body.error.extensions) == {"param": None}
    assert dict(body.extensions) == {"request": "trace-1"}


def test_error_type_and_code_may_be_absent_or_null() -> None:
    """Verify both optional members are nullable and read as None."""
    absent = OpenAIChatCompletionErrorDTO.from_json({"message": "m"})
    null = OpenAIChatCompletionErrorDTO.from_json(
        {"message": "m", "type": None, "code": None}
    )

    assert (absent.type, absent.code) == (None, None)
    assert (null.type, null.code) == (None, None)


def test_error_code_keeps_integer_codes_exactly() -> None:
    """Verify an integer code is kept as an integer, not as text."""
    error = OpenAIChatCompletionErrorDTO.from_json({"message": "m", "code": 1013})

    assert error.code == 1013
    assert type(error.code) is int


def test_error_rejects_invalid_member_kinds_with_locations() -> None:
    """Verify each member kind is checked and located in the failure body."""
    assert _failure_message({"error": {"type": "t"}}) == (
        "OpenAI-compatible response field /error/message must be a string."
    )
    assert _failure_message({"error": {"message": "m", "type": 3}}) == (
        "OpenAI-compatible response field /error/type must be a string or null."
    )
    assert _failure_message({"error": {"message": "m", "code": True}}) == (
        "OpenAI-compatible response field /error/code must be a string, "
        "an integer, or null."
    )
    assert _failure_message({"error": {"message": "m", "code": 1.5}}) == (
        "OpenAI-compatible response field /error/code must be a string, "
        "an integer, or null."
    )


def test_failure_body_requires_an_error_object() -> None:
    """Verify the error member is required, not nullable, and an object."""
    expected = "OpenAI-compatible response field /error must be an object."

    assert _failure_message({}) == expected
    assert _failure_message({"error": None}) == expected
    assert _failure_message({"error": "boom"}) == expected
    assert _failure_message(["boom"]) == (
        "OpenAI-compatible response field / must be an object."
    )


def test_error_construction_requires_frozen_member_types() -> None:
    """Verify direct construction rejects values the wire cannot carry."""
    message_error = _capture(lambda: OpenAIChatCompletionErrorDTO(cast(str, None)))
    type_error = _capture(lambda: OpenAIChatCompletionErrorDTO("m", cast(str, 1)))
    bool_error = _capture(
        lambda: OpenAIChatCompletionErrorDTO("m", code=cast(int, True))
    )
    unsafe_error = _capture(lambda: OpenAIChatCompletionErrorDTO("m", code=2**53))
    body_error = _capture(
        lambda: OpenAIChatCompletionErrorResponseDTO(
            cast(OpenAIChatCompletionErrorDTO, {"message": "m"})
        )
    )

    assert isinstance(message_error, TypeError)
    assert isinstance(type_error, TypeError)
    assert isinstance(bool_error, TypeError)
    assert str(bool_error) == (
        "OpenAIChatCompletionErrorDTO code must be a string, an integer, or None."
    )
    assert isinstance(unsafe_error, ValueError)
    assert isinstance(body_error, TypeError)


def test_failure_values_are_frozen() -> None:
    """Verify decoded failure values cannot be changed by later consumers."""
    body = OpenAIChatCompletionErrorResponseDTO(OpenAIChatCompletionErrorDTO("m"))

    body_error = _capture(lambda: setattr(body, "error", None))
    error_error = _capture(lambda: setattr(body.error, "code", "x"))

    assert isinstance(body_error, FrozenInstanceError)
    assert isinstance(error_error, FrozenInstanceError)
