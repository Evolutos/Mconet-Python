"""OpenAI-compatible text conversation integration module."""

# Wire DTOs stay in private modules so that the protocol JSON shape never becomes
# a public SDK contract; only the adapter and its frozen protocol id are exported.
from mconet.integration.openai_compatible.openai_chat_completions_adapter import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)

__all__: tuple[str, ...] = (
    "OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID",
    "OpenAIChatCompletionsAdapter",
)
