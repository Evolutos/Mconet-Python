"""Tests for the OpenAI-compatible chat completions adapter."""

from dataclasses import dataclass, field
from typing import Literal

from mconet.core.domain import (
    ConversationTaskResult,
    Extensions,
    MediaType,
    MessageDocument,
    MessageElementKind,
    MessageGroup,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
)
from mconet.core.spi import ComponentTypePort
from mconet.integration.openai_compatible.openai_chat_completions_adapter import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)

_JSON = MediaType("application", "json")
_JSON_VALUE = OpenIdentifier("json.value")
_SERVICE_ID = OpenIdentifier("service.vendor")
_UNARY = OpenIdentifier("unary")
_CONVERSATION = OpenIdentifier("conversation.generate")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for fixtures."""
    return {}


def _model() -> ModelDescriptor:
    """Return the requested fixture model."""
    return NamedModel("fixture-model")


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete ModelTarget for adapter tests."""

    protocol_id: OpenIdentifier = OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
    service_id: OpenIdentifier = _SERVICE_ID
    model: ModelDescriptor = field(default_factory=_model)
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Complete InteractionMode for adapter tests."""

    id: OpenIdentifier = _UNARY


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete TaskDescriptor for adapter tests."""

    type: OpenIdentifier = _CONVERSATION
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Kind:
    """Complete MessageElementKind for fixture documents."""

    id: OpenIdentifier
    category: str = "group"
    composition: Literal["leaf", "container"] = "container"


def test_descriptor_declares_json_value_ports() -> None:
    """Verify the adapter ports connect to the JSON codec ports."""
    descriptor = OpenAIChatCompletionsAdapter().descriptor

    assert descriptor.name == "openai-chat-completions-adapter"
    assert descriptor.version == "1.0.0"
    assert descriptor.source == "builtin"
    assert descriptor.capabilities == frozenset()
    assert descriptor.type_contract is not None
    assert descriptor.type_contract.inputs == (
        ComponentTypePort("response", _JSON_VALUE, None, _JSON),
        ComponentTypePort("error", _JSON_VALUE, None, _JSON),
    )
    assert descriptor.type_contract.outputs == (
        ComponentTypePort("payload", _JSON_VALUE, None, _JSON),
    )
    assert OpenAIChatCompletionsAdapter().descriptor is descriptor


def test_supports_the_chat_completions_protocol_for_any_service_and_model() -> None:
    """Verify the protocol id selects the adapter, not the service or model."""
    adapter = OpenAIChatCompletionsAdapter()
    other_service = _Target(
        service_id=OpenIdentifier("service.other"),
        model=NamedModel("another-model"),
        deployment_id="east",
    )

    assert adapter.supports(_Target(), _Task(), _Mode()) is True
    assert adapter.supports(other_service, _Task(), _Mode()) is True


def test_does_not_support_another_protocol() -> None:
    """Verify protocol identity is matched exactly."""
    adapter = OpenAIChatCompletionsAdapter()

    for protocol_id in ("openai.responses", "openai.chat-completions.v2", "openai"):
        target = _Target(protocol_id=OpenIdentifier(protocol_id))
        assert adapter.supports(target, _Task(), _Mode()) is False


def test_does_not_support_another_task_type() -> None:
    """Verify only conversation generation is handled."""
    adapter = OpenAIChatCompletionsAdapter()

    for task_type in ("embedding.generate", "conversation.summarize"):
        task = _Task(type=OpenIdentifier(task_type))
        assert adapter.supports(_Target(), task, _Mode()) is False


def test_does_not_support_another_interaction_mode() -> None:
    """Verify only unary mode is handled."""
    adapter = OpenAIChatCompletionsAdapter()

    for mode_id in ("streaming", "batch"):
        assert adapter.supports(_Target(), _Task(), _Mode(OpenIdentifier(mode_id))) is (
            False
        )


def test_supports_the_descriptor_of_a_real_conversation_result() -> None:
    """Verify the standard conversation descriptor is recognized."""
    root = MessageGroup("root", _root_kind(), ())
    descriptor = ConversationTaskResult(
        MessageDocument("1.0", "output", root)
    ).descriptor

    assert OpenAIChatCompletionsAdapter().supports(_Target(), descriptor, _Mode())


def _root_kind() -> MessageElementKind:
    """Return the standard message root kind."""
    return _Kind(OpenIdentifier("message.root"))
