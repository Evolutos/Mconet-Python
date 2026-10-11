"""OpenAI-compatible text conversation integration module."""

from mconet.integration.openai_compatible.openai_chat_completion_choice_dto import (
    OpenAIChatCompletionChoiceDTO,
)
from mconet.integration.openai_compatible.openai_chat_completion_request_dto import (
    OpenAIChatCompletionRequestDTO,
)
from mconet.integration.openai_compatible.openai_chat_completion_response_dto import (
    OpenAIChatCompletionResponseDTO,
)
from mconet.integration.openai_compatible.openai_chat_completion_usage_dto import (
    OpenAIChatCompletionUsageDTO,
)
from mconet.integration.openai_compatible.openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)

__all__: tuple[str, ...] = (
    "OpenAIChatCompletionChoiceDTO",
    "OpenAIChatCompletionRequestDTO",
    "OpenAIChatCompletionResponseDTO",
    "OpenAIChatCompletionUsageDTO",
    "OpenAIChatMessageDTO",
)
