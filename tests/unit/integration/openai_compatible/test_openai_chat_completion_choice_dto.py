"""Tests for the OpenAI-compatible chat completion choice wire value."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import JsonValue, ModelInteractionError
from mconet.integration.openai_compatible._openai_chat_completion_choice_dto import (
    OpenAIChatCompletionChoiceDTO,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _failure_message(value: JsonValue) -> str:
    """Return the protocol failure message for one decoded choice."""
    error = _capture(
        lambda: OpenAIChatCompletionChoiceDTO.from_json(value, "/choices/0")
    )
    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_protocol_response"
    assert error.phase.id.value == "response_parsing"
    return error.message


def test_choice_reads_index_message_reason_and_unknown_members() -> None:
    """Verify the frozen members map and extra members are captured."""
    decoded: JsonValue = {
        "index": 0,
        "message": {"role": "assistant", "content": "Hi", "refusal": None},
        "logprobs": None,
        "finish_reason": "stop",
    }

    choice = OpenAIChatCompletionChoiceDTO.from_json(decoded, "/choices/0")

    assert choice.index == 0
    assert choice.message == OpenAIChatMessageDTO("assistant", "Hi", {"refusal": None})
    assert choice.finish_reason == "stop"
    assert dict(choice.extensions) == {"logprobs": None}


def test_choice_keeps_an_unknown_finish_reason_exactly() -> None:
    """Verify reason interpretation is left to the response mapping."""
    choice = OpenAIChatCompletionChoiceDTO.from_json(
        {
            "index": 2,
            "message": {"role": "assistant", "content": ""},
            "finish_reason": "Vendor_Specific",
        }
    )

    assert choice.index == 2
    assert choice.finish_reason == "Vendor_Specific"
    assert dict(choice.extensions) == {}


def test_choice_reports_the_nested_message_location() -> None:
    """Verify message failures carry the choice-relative pointer."""
    message = _failure_message(
        {"index": 0, "message": {"role": "assistant"}, "finish_reason": "stop"}
    )

    assert message == (
        "OpenAI-compatible response field /choices/0/message/content must be a string."
    )


def test_choice_requires_a_non_negative_integer_index() -> None:
    """Verify booleans, floats, nulls, and negatives are rejected."""
    expected = (
        "OpenAI-compatible response field /choices/0/index "
        "must be a non-negative integer."
    )
    for index in (None, True, 0.0, -1, "0"):
        decoded: JsonValue = {
            "index": index,
            "message": {"role": "assistant", "content": ""},
            "finish_reason": "stop",
        }
        assert _failure_message(decoded) == expected
    assert (
        _failure_message(
            {"message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}
        )
        == expected
    )


def test_choice_requires_a_message_object_and_a_reason_string() -> None:
    """Verify missing message and null finish_reason fail at their pointers."""
    missing_message = _failure_message({"index": 0, "finish_reason": "stop"})
    null_reason = _failure_message(
        {
            "index": 0,
            "message": {"role": "assistant", "content": ""},
            "finish_reason": None,
        }
    )
    non_object = _failure_message([])

    assert missing_message == (
        "OpenAI-compatible response field /choices/0/message must be an object."
    )
    assert null_reason == (
        "OpenAI-compatible response field /choices/0/finish_reason must be a string."
    )
    assert non_object == (
        "OpenAI-compatible response field /choices/0 must be an object."
    )


def test_choice_construction_requires_frozen_member_types() -> None:
    """Verify direct construction rejects values the wire cannot carry."""
    message = OpenAIChatMessageDTO("assistant", "")
    bool_error = _capture(
        lambda: OpenAIChatCompletionChoiceDTO(cast(int, True), message, "stop")
    )
    negative_error = _capture(
        lambda: OpenAIChatCompletionChoiceDTO(-1, message, "stop")
    )
    message_error = _capture(
        lambda: OpenAIChatCompletionChoiceDTO(
            0, cast(OpenAIChatMessageDTO, {"role": "assistant"}), "stop"
        )
    )
    reason_error = _capture(
        lambda: OpenAIChatCompletionChoiceDTO(0, message, cast(str, None))
    )

    assert isinstance(bool_error, TypeError)
    assert isinstance(negative_error, ValueError)
    assert isinstance(message_error, TypeError)
    assert isinstance(reason_error, TypeError)
    assert str(reason_error) == (
        "OpenAIChatCompletionChoiceDTO finish_reason must be a string."
    )


def test_choice_is_frozen() -> None:
    """Verify a decoded choice cannot be changed by later consumers."""
    choice = OpenAIChatCompletionChoiceDTO(
        0, OpenAIChatMessageDTO("assistant", ""), "stop"
    )

    error = _capture(lambda: setattr(choice, "finish_reason", "length"))

    assert isinstance(error, FrozenInstanceError)
