"""OpenAI-compatible text conversation integration module."""

from mconet.integration.openai_compatible.openai_chat_completion_request_dto import (
    OpenAIChatCompletionRequestDTO,
)
from mconet.integration.openai_compatible.openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)

__all__: tuple[str, ...] = (
    "OpenAIChatCompletionRequestDTO",
    "OpenAIChatMessageDTO",
)
