"""Tests for the integration-openai-compatible module boundary."""

import mconet.integration.openai_compatible
from mconet.integration.openai_compatible import (
    OpenAIChatCompletionChoiceDTO,
    OpenAIChatCompletionRequestDTO,
    OpenAIChatMessageDTO,
)


def test_openai_compatible_exports_the_defined_protocol_values() -> None:
    """Verify the module publishes exactly the protocol values defined so far."""
    module = mconet.integration.openai_compatible

    assert module.__all__ == (
        "OpenAIChatCompletionChoiceDTO",
        "OpenAIChatCompletionRequestDTO",
        "OpenAIChatMessageDTO",
    )
    assert module.OpenAIChatCompletionChoiceDTO is OpenAIChatCompletionChoiceDTO
    assert module.OpenAIChatCompletionRequestDTO is OpenAIChatCompletionRequestDTO
    assert module.OpenAIChatMessageDTO is OpenAIChatMessageDTO
