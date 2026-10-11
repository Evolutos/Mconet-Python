"""OpenAI-compatible text conversation integration module."""

from mconet.integration.openai_compatible.openai_chat_completion_choice_dto import (
    OpenAIChatCompletionChoiceDTO,
)
from mconet.integration.openai_compatible.openai_chat_completion_error_dto import (
    OpenAIChatCompletionErrorDTO,
)
from mconet.integration.openai_compatible.openai_chat_completion_error_response_dto import (
    OpenAIChatCompletionErrorResponseDTO,
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
    "OpenAIChatCompletionErrorDTO",
    "OpenAIChatCompletionErrorResponseDTO",
    "OpenAIChatCompletionRequestDTO",
    "OpenAIChatCompletionResponseDTO",
    "OpenAIChatCompletionUsageDTO",
    "OpenAIChatMessageDTO",
)
