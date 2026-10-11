"""Tests for the integration-openai-compatible module boundary."""

import mconet.integration.openai_compatible
from mconet.core.domain import OpenIdentifier
from mconet.core.spi import TaskProtocolAdapter
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionChoiceDTO,
    OpenAIChatCompletionErrorDTO,
    OpenAIChatCompletionErrorResponseDTO,
    OpenAIChatCompletionRequestDTO,
    OpenAIChatCompletionResponseDTO,
    OpenAIChatCompletionsAdapter,
    OpenAIChatCompletionUsageDTO,
    OpenAIChatMessageDTO,
)


def test_openai_compatible_exports_the_adapter_and_protocol_values() -> None:
    """Verify the module publishes exactly the adapter and its wire values."""
    module = mconet.integration.openai_compatible

    assert module.__all__ == (
        "OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID",
        "OpenAIChatCompletionChoiceDTO",
        "OpenAIChatCompletionErrorDTO",
        "OpenAIChatCompletionErrorResponseDTO",
        "OpenAIChatCompletionRequestDTO",
        "OpenAIChatCompletionResponseDTO",
        "OpenAIChatCompletionUsageDTO",
        "OpenAIChatCompletionsAdapter",
        "OpenAIChatMessageDTO",
    )
    assert module.OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID is (
        OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
    )
    assert module.OpenAIChatCompletionChoiceDTO is OpenAIChatCompletionChoiceDTO
    assert module.OpenAIChatCompletionErrorDTO is OpenAIChatCompletionErrorDTO
    assert (
        module.OpenAIChatCompletionErrorResponseDTO
        is OpenAIChatCompletionErrorResponseDTO
    )
    assert module.OpenAIChatCompletionRequestDTO is OpenAIChatCompletionRequestDTO
    assert module.OpenAIChatCompletionResponseDTO is OpenAIChatCompletionResponseDTO
    assert module.OpenAIChatCompletionUsageDTO is OpenAIChatCompletionUsageDTO
    assert module.OpenAIChatCompletionsAdapter is OpenAIChatCompletionsAdapter
    assert module.OpenAIChatMessageDTO is OpenAIChatMessageDTO


def test_adapter_implements_the_task_protocol_adapter_contract() -> None:
    """Verify the exported adapter conforms structurally and statically."""
    adapter: TaskProtocolAdapter = OpenAIChatCompletionsAdapter()

    assert isinstance(adapter, TaskProtocolAdapter)
    assert OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID == OpenIdentifier(
        "openai.chat-completions"
    )
