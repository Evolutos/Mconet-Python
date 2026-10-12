"""Text conversion produces one complete conversation model request."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.client.text_request import model_request_from_text
from mconet.core.domain import (
    ConversationInputNode,
    ConversationTaskRequest,
    Extensions,
    MessageEntry,
    MessageGroup,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    TextMessageContent,
)


def _empty_extensions() -> Extensions:
    """Return one independent empty extension mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target retained by the generated request."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_text_conversion_builds_a_user_message_request() -> None:
    """Verify one prompt becomes a conversation request and nothing is sent."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    request = model_request_from_text(target, "  Hello  ")
    task = cast(ConversationTaskRequest, request.task)
    task_root = task.document.root
    conversation_input = cast(ConversationInputNode, task_root.children[0])
    message_root = conversation_input.messages.root
    current = cast(MessageGroup, message_root.sub_elements[0])
    entry = cast(MessageEntry, current.sub_elements[0])
    content = cast(TextMessageContent, entry.content[0])

    assert request.target is target
    assert request.service_access is None
    assert conversation_input.messages.purpose == "input"
    assert message_root.kind.id.value == "message.root"
    assert current.kind.id.value == "message.current"
    assert entry.role.id.value == "message.user"
    assert content.text == "  Hello  "
    assert not hasattr(model_request_from_text, "send")


def test_text_conversion_rejects_a_non_string() -> None:
    """Verify a non-string prompt fails before a request exists."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    try:
        model_request_from_text(target, cast(str, object()))
    except TypeError as error:
        assert "text must be a string" in str(error)
    else:
        raise AssertionError("Expected a non-string prompt to be rejected.")
