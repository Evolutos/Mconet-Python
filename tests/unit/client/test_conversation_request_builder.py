"""ConversationRequestBuilder constructs a domain request only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.client.conversation_request_builder import ConversationRequestBuilder
from mconet.core.domain import (
    ConversationInputNode,
    ConversationTaskBuilder,
    ConversationTaskRequest,
    Extensions,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelDescriptor,
    ModelRequestBuilder,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TextMessageContent,
)


def _empty_extensions() -> Extensions:
    """Return one independent empty extension mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target retained by the built request."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for the task root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Container kind for one message group."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Role:
    """User role for one text message."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def _task() -> ConversationTaskRequest:
    """Build one text conversation task."""
    role: MessageRole = _Role(OpenIdentifier("message.user"))
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    entry = MessageEntry(
        "message-entry",
        role,
        (TextMessageContent("text-content", "Hello"),),
    )
    messages = MessageDocument(
        "1.0",
        "input",
        MessageGroup("message-root", kind, (entry,)),
    )
    document = TaskDocument(
        "1.0",
        TaskGroupNode(
            "root",
            _NodeKind(OpenIdentifier("task.root"), "container"),
            (ConversationInputNode("input", messages),),
        ),
    )
    return ConversationTaskBuilder(document).build()


def _target() -> ModelTarget:
    """Return one structural model target."""
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )


def test_builder_matches_the_domain_request_and_ignores_protocol_components() -> None:
    """Verify the conversation builder returns the same domain request shape."""
    target = _target()
    task = _task()
    metadata = {"locale": "zh-CN"}
    built = ConversationRequestBuilder(target, task).with_metadata(metadata).build()
    direct = ModelRequestBuilder(target, task).with_metadata(metadata).build()

    assert built.target is target
    assert built.task is task
    assert built.metadata == direct.metadata
    assert built.service_access is None
    for name in ("prepare_plan", "encode", "send", "interact"):
        assert not hasattr(ConversationRequestBuilder, name)


def test_builder_rejects_a_non_conversation_task() -> None:
    """Verify another task family cannot enter the conversation builder."""
    try:
        ConversationRequestBuilder(_target(), cast(ConversationTaskRequest, object()))
    except TypeError as error:
        assert "ConversationTaskRequest" in str(error)
    else:
        raise AssertionError("Expected a non-conversation task to be rejected.")
