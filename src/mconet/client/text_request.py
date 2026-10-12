"""Convert one text prompt into a complete conversation model request."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, cast

from mconet.client.conversation_request_builder import ConversationRequestBuilder
from mconet.core.domain.conversation_input_node import ConversationInputNode
from mconet.core.domain.conversation_task_builder import ConversationTaskBuilder
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_entry import MessageEntry
from mconet.core.domain.message_group import MessageGroup
from mconet.core.domain.message_role import MessageRole
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.domain.task_document import TaskDocument
from mconet.core.domain.task_group_node import TaskGroupNode
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.text_message_content import TextMessageContent

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_USER_ROLE_ID = OpenIdentifier("message.user")
_ROOT_KIND_ID = OpenIdentifier("message.root")
_CURRENT_KIND_ID = OpenIdentifier("message.current")
_TASK_ROOT_KIND_ID = OpenIdentifier("task.root")


@dataclass(frozen=True, slots=True)
class _Role:
    """User role stored on the generated message entry."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Container kind for one generated message group."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Container kind for the generated task root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"]


_USER_ROLE: MessageRole = _Role(_USER_ROLE_ID)
_ROOT_KIND: MessageElementKind = _MessageKind(_ROOT_KIND_ID, "group", "container")
_CURRENT_KIND: MessageElementKind = _MessageKind(
    _CURRENT_KIND_ID,
    "group",
    "container",
)
_TASK_ROOT_KIND: TaskNodeKind = _TaskKind(_TASK_ROOT_KIND_ID, "container")


def model_request_from_text(
    target: ModelTarget,
    text: str,
    service_access: ServiceAccess | None = None,
) -> ModelRequest:
    """Build one complete conversation request from a text prompt.

    The request contains one conversation task. Its input document has a
    ``message.root`` group, a ``message.current`` group, and one
    ``message.user`` entry whose text is the supplied prompt. Service access
    is stored only when the caller supplies it. This function does not plan,
    encode, authorize, or send.

    Args:
        target: Routing target retained by the request.
        text: Exact user text. It is not trimmed.
        service_access: Optional unresolved access for this request.

    Returns:
        A validated model request.

    Raises:
        TypeError: If an argument has an invalid nominal type.
        ValueError: If the target, text, or access is semantically invalid.
        ModelInteractionError: If the generated conversation exceeds R1 scope.
    """
    candidate_target = cast(object, target)
    candidate_text = cast(object, text)
    candidate_access = cast(object, service_access)
    if not isinstance(candidate_target, ModelTarget):
        raise TypeError("target must implement ModelTarget.")
    if type(candidate_text) is not str:
        raise TypeError("text must be a string.")
    if candidate_access is not None and not isinstance(candidate_access, ServiceAccess):
        raise TypeError("service_access must implement ServiceAccess or be None.")

    entry = MessageEntry(
        "message-entry",
        _USER_ROLE,
        (TextMessageContent("text-content", candidate_text),),
    )
    current = MessageGroup("message-current", _CURRENT_KIND, (entry,))
    root = MessageGroup("message-root", _ROOT_KIND, (current,))
    messages = MessageDocument("1.0", "input", root)
    document = TaskDocument(
        "1.0",
        TaskGroupNode(
            "root",
            _TASK_ROOT_KIND,
            (ConversationInputNode("input", messages),),
        ),
    )
    task = ConversationTaskBuilder(document).build()
    builder = ConversationRequestBuilder(candidate_target, task)
    if candidate_access is not None:
        builder.with_service_access(candidate_access)
    return builder.build()
