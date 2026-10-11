"""Tests for the integration-openai-compatible module boundary."""

import mconet.integration.openai_compatible
from mconet.core.domain import OpenIdentifier
from mconet.core.spi import TaskProtocolAdapter
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)

_PRIVATE_DTO_NAMES = (
    "OpenAIChatCompletionChoiceDTO",
    "OpenAIChatCompletionErrorDTO",
    "OpenAIChatCompletionErrorResponseDTO",
    "OpenAIChatCompletionRequestDTO",
    "OpenAIChatCompletionResponseDTO",
    "OpenAIChatCompletionUsageDTO",
    "OpenAIChatMessageDTO",
)


def test_openai_compatible_exports_only_the_adapter_and_protocol_id() -> None:
    """Verify the module publishes the adapter and keeps wire DTOs private."""
    module = mconet.integration.openai_compatible

    assert module.__all__ == (
        "OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID",
        "OpenAIChatCompletionsAdapter",
    )
    assert module.OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID is (
        OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
    )
    assert module.OpenAIChatCompletionsAdapter is OpenAIChatCompletionsAdapter
    for name in _PRIVATE_DTO_NAMES:
        assert not hasattr(module, name)


def test_adapter_implements_the_task_protocol_adapter_contract() -> None:
    """Verify the exported adapter conforms structurally and statically."""
    adapter: TaskProtocolAdapter = OpenAIChatCompletionsAdapter()

    assert isinstance(adapter, TaskProtocolAdapter)
    assert OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID == OpenIdentifier(
        "openai.chat-completions"
    )
