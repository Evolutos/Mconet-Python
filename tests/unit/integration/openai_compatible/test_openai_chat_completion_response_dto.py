"""Tests for the OpenAI-compatible successful response wire value."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import JsonValue, ModelInteractionError
from mconet.integration.openai_compatible import (
    OpenAIChatCompletionChoiceDTO,
    OpenAIChatCompletionResponseDTO,
    OpenAIChatCompletionUsageDTO,
    OpenAIChatMessageDTO,
)

_CHOICE: JsonValue = {
    "index": 0,
    "message": {"role": "assistant", "content": "Hi"},
    "finish_reason": "stop",
}


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _failure_message(value: JsonValue) -> str:
    """Return the protocol failure message for one decoded response body."""
    error = _capture(lambda: OpenAIChatCompletionResponseDTO.from_json(value))
    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_protocol_response"
    return error.message


def test_response_reads_frozen_members_and_captures_the_rest() -> None:
    """Verify id, model, choices, and usage map and extras are captured."""
    decoded: JsonValue = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1_800_000_000,
        "model": "model-a-2026",
        "choices": [_CHOICE],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        "system_fingerprint": "fp_1",
    }

    response = OpenAIChatCompletionResponseDTO.from_json(decoded)

    assert response.id == "chatcmpl-1"
    assert response.model == "model-a-2026"
    assert response.choices == (
        OpenAIChatCompletionChoiceDTO(
            0, OpenAIChatMessageDTO("assistant", "Hi"), "stop"
        ),
    )
    assert response.usage == OpenAIChatCompletionUsageDTO(3, 1, 4)
    assert dict(response.extensions) == {
        "object": "chat.completion",
        "created": 1_800_000_000,
        "system_fingerprint": "fp_1",
    }


def test_response_optional_members_are_none_when_absent() -> None:
    """Verify only choices is required."""
    response = OpenAIChatCompletionResponseDTO.from_json({"choices": [_CHOICE]})

    assert response.id is None
    assert response.model is None
    assert response.usage is None
    assert dict(response.extensions) == {}


def test_response_keeps_empty_and_multiple_choices_in_service_order() -> None:
    """Verify choice-count policy is left to the response mapping."""
    second: JsonValue = {
        "index": 1,
        "message": {"role": "assistant", "content": "Second"},
        "finish_reason": "length",
    }

    empty = OpenAIChatCompletionResponseDTO.from_json({"choices": []})
    many = OpenAIChatCompletionResponseDTO.from_json({"choices": [second, _CHOICE]})

    assert empty.choices == ()
    assert [choice.index for choice in many.choices] == [1, 0]


def test_response_reports_nested_choice_locations() -> None:
    """Verify a bad choice is located by its array index."""
    message = _failure_message(
        {"choices": [_CHOICE, {"index": 1, "finish_reason": "stop"}]}
    )

    assert message == (
        "OpenAI-compatible response field /choices/1/message must be an object."
    )


def test_response_rejects_missing_or_non_array_choices() -> None:
    """Verify choices is required and must be an array."""
    expected = "OpenAI-compatible response field /choices must be an array."

    assert _failure_message({}) == expected
    assert _failure_message({"choices": None}) == expected
    assert _failure_message({"choices": {"0": _CHOICE}}) == expected


def test_response_rejects_null_optional_members() -> None:
    """Verify optional members are not nullable when present."""
    id_message = _failure_message({"id": None, "choices": []})
    model_message = _failure_message({"model": 5, "choices": []})
    usage_message = _failure_message({"usage": None, "choices": []})

    assert id_message == "OpenAI-compatible response field /id must be a string."
    assert model_message == (
        "OpenAI-compatible response field /model must be a string."
    )
    assert usage_message == (
        "OpenAI-compatible response field /usage must be an object."
    )


def test_response_reports_the_first_invalid_member_in_profile_order() -> None:
    """Verify failure precedence follows id, model, choices, then usage."""
    message = _failure_message({"usage": None, "choices": None, "model": 1})

    assert message == "OpenAI-compatible response field /model must be a string."


def test_response_rejects_a_non_object_body() -> None:
    """Verify the body itself must be an object."""
    assert _failure_message([_CHOICE]) == (
        "OpenAI-compatible response field / must be an object."
    )


def test_response_construction_requires_frozen_member_types() -> None:
    """Verify direct construction rejects values the wire cannot carry."""
    list_error = _capture(
        lambda: OpenAIChatCompletionResponseDTO(
            cast(tuple[OpenAIChatCompletionChoiceDTO, ...], [])
        )
    )
    member_error = _capture(
        lambda: OpenAIChatCompletionResponseDTO(
            cast(tuple[OpenAIChatCompletionChoiceDTO, ...], (_CHOICE,))
        )
    )
    id_error = _capture(lambda: OpenAIChatCompletionResponseDTO((), id=cast(str, 1)))
    usage_error = _capture(
        lambda: OpenAIChatCompletionResponseDTO(
            (), usage=cast(OpenAIChatCompletionUsageDTO, {})
        )
    )

    assert isinstance(list_error, TypeError)
    assert isinstance(member_error, TypeError)
    assert isinstance(id_error, TypeError)
    assert str(id_error) == (
        "OpenAIChatCompletionResponseDTO id must be a string or None."
    )
    assert isinstance(usage_error, TypeError)


def test_response_is_frozen() -> None:
    """Verify a decoded response cannot be changed by later consumers."""
    response = OpenAIChatCompletionResponseDTO(())

    error = _capture(lambda: setattr(response, "model", "other"))

    assert isinstance(error, FrozenInstanceError)
