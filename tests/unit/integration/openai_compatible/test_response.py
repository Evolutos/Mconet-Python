"""Tests for mapping OpenAI-compatible response wire values to domain facts."""

from collections.abc import Callable

from mconet.core.domain import (
    ConversationTaskResult,
    MessageEntry,
    ModelInteractionError,
    OpenIdentifier,
    TextMessageContent,
    TokenUsage,
    validate_message_document,
    validate_model_descriptor,
)
from mconet.integration.openai_compatible._openai_chat_completion_choice_dto import (
    OpenAIChatCompletionChoiceDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_response_dto import (
    OpenAIChatCompletionResponseDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_usage_dto import (
    OpenAIChatCompletionUsageDTO,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)
from mconet.integration.openai_compatible._response import (
    output_messages,
    output_status,
    resolved_model,
    single_choice,
    token_usage,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _choice(
    index: int = 0, role: str = "assistant", content: str = "Hi"
) -> OpenAIChatCompletionChoiceDTO:
    """Create one choice with a stop finish reason."""
    return OpenAIChatCompletionChoiceDTO(
        index, OpenAIChatMessageDTO(role, content), "stop"
    )


def _assert_protocol_error(error: BaseException, message: str) -> None:
    """Require the shared protocol failure for a response field."""
    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "protocol"
    assert error.phase.id.value == "response_parsing"
    assert error.code == "invalid_protocol_response"
    assert error.message == message


def test_single_choice_returns_the_only_choice() -> None:
    """Verify one choice is selected as is."""
    choice = _choice()

    assert single_choice(OpenAIChatCompletionResponseDTO((choice,))) is choice


def test_single_choice_rejects_zero_or_several_choices() -> None:
    """Verify no selection rule is invented for other choice counts."""
    for choices in ((), (_choice(0), _choice(1))):
        response = OpenAIChatCompletionResponseDTO(choices)

        error = _capture(lambda response=response: single_choice(response))

        _assert_protocol_error(
            error,
            "OpenAI-compatible response field /choices "
            "must contain exactly one choice.",
        )


def test_output_messages_builds_one_valid_output_document() -> None:
    """Verify the document shape, IDs, role, and exact text."""
    text = "  \u4f60\u597d\n\U0001f30d e\u0301 "
    message = OpenAIChatMessageDTO(
        "assistant", text, extensions={"refusal": None, "annotations": []}
    )
    choice = OpenAIChatCompletionChoiceDTO(0, message, "stop")

    document = output_messages(choice)

    assert validate_message_document(document) is document
    assert document.version == "1.0"
    assert document.purpose == "output"
    assert document.root.id == "root"
    assert document.root.kind.id == OpenIdentifier("message.root")
    (entry,) = document.root.sub_elements
    assert isinstance(entry, MessageEntry)
    assert entry.id == "choice-0"
    assert entry.role.id == OpenIdentifier("message.assistant")
    assert entry.role.raw_value == "assistant"
    assert entry.content == (TextMessageContent("choice-0-text", text),)
    assert dict(entry.extensions) == {"refusal": None, "annotations": []}
    assert ConversationTaskResult(document).text == text


def test_output_messages_keeps_an_empty_text() -> None:
    """Verify empty content stays one empty text value."""
    document = output_messages(_choice(content=""))

    (entry,) = document.root.sub_elements
    assert isinstance(entry, MessageEntry)
    assert entry.content == (TextMessageContent("choice-0-text", ""),)


def test_output_messages_rejects_an_unknown_role() -> None:
    """Verify an unknown role is located at the single choice."""
    error = _capture(lambda: output_messages(_choice(role="tool")))

    _assert_protocol_error(
        error,
        "OpenAI-compatible response field /choices/0/message/role "
        "must be assistant, system, or user.",
    )


def test_finish_reasons_map_to_standard_statuses() -> None:
    """Verify each mapped finish reason and the open fallback."""
    expected = {
        "stop": "completed",
        "length": "incomplete",
        "content_filter": "filtered",
        "tool_calls": "requires_action",
        "function_call": "requires_action",
        "STOP": "unknown",
        "": "unknown",
        "vendor_paused": "unknown",
    }

    for finish_reason, status in expected.items():
        assert output_status(finish_reason).id.value == status


def test_token_usage_copies_counts_without_computing_any() -> None:
    """Verify counts map one to one and absence is kept."""
    usage = OpenAIChatCompletionUsageDTO(
        37, 12, 50, extensions={"prompt_tokens_details": {"cached_tokens": 8}}
    )

    assert token_usage(usage) == TokenUsage(
        37, 12, 50, extensions={"prompt_tokens_details": {"cached_tokens": 8}}
    )
    assert token_usage(OpenAIChatCompletionUsageDTO(completion_tokens=0)) == (
        TokenUsage(output_tokens=0)
    )
    assert token_usage(None) is None


def test_resolved_model_keeps_the_reported_name_exactly() -> None:
    """Verify the name is copied and absence is not filled in."""
    model = resolved_model("gpt-4o-2024-08-06")

    assert model is not None
    assert validate_model_descriptor(model) is model
    assert model.name == "gpt-4o-2024-08-06"
    assert model.display_name is None
    assert model.family is None
    assert resolved_model(None) is None


def test_resolved_model_rejects_an_empty_name() -> None:
    """Verify a name no descriptor can carry is a protocol error."""
    for name in ("", "  "):
        error = _capture(lambda name=name: resolved_model(name))

        _assert_protocol_error(
            error,
            "OpenAI-compatible response field /model must not be empty or whitespace.",
        )
