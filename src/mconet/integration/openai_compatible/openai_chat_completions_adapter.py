"""Task protocol adapter for OpenAI-compatible text chat completions."""

from __future__ import annotations

from mconet.core.domain import (
    InteractionMode,
    MediaType,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
)

OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID = OpenIdentifier("openai.chat-completions")
"""Protocol identifier a ModelTarget names to select this adapter."""

_CONVERSATION_TASK_TYPE = OpenIdentifier("conversation.generate")
_UNARY_MODE_ID = OpenIdentifier("unary")
_JSON_VALUE_TYPE_ID = OpenIdentifier("json.value")
_JSON_MEDIA_TYPE = MediaType("application", "json")

_ADAPTER_TYPE_CONTRACT = ComponentTypeContract(
    inputs=(
        ComponentTypePort("response", _JSON_VALUE_TYPE_ID, None, _JSON_MEDIA_TYPE),
        ComponentTypePort("error", _JSON_VALUE_TYPE_ID, None, _JSON_MEDIA_TYPE),
    ),
    outputs=(
        ComponentTypePort("payload", _JSON_VALUE_TYPE_ID, None, _JSON_MEDIA_TYPE),
    ),
)

_ADAPTER_DESCRIPTOR = ComponentDescriptor(
    "openai-chat-completions-adapter",
    "1.0.0",
    "builtin",
    _ADAPTER_TYPE_CONTRACT,
)


class OpenAIChatCompletionsAdapter:
    """Map conversation tasks to the OpenAI-compatible chat completions API.

    The adapter is stateless. It handles exactly one combination: a target
    whose protocol is ``openai.chat-completions``, the
    ``conversation.generate`` task, and the ``unary`` interaction mode. Any
    service and model may use the protocol, so neither is part of matching.

    Its payload output and both decoded inputs are ``json.value`` values of
    media type ``application/json``, matching the JSON codec ports.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared diagnostic metadata and JSON type contract."""
        return _ADAPTER_DESCRIPTOR

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return whether the target, task, and mode are the handled tuple.

        Each identifier is compared exactly. Service, model, deployment, task
        version, and extensions are not consulted, and no I/O happens.

        Args:
            target: Model target being matched.
            task: Descriptor of the requested task.
            mode: Requested interaction mode.

        Returns:
            ``True`` only for the chat completions protocol, the conversation
            generation task, and unary mode.
        """
        return (
            target.protocol_id == OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
            and task.type == _CONVERSATION_TASK_TYPE
            and mode.id == _UNARY_MODE_ID
        )
