"""Full requests, the conversation builder, and the text API encode alike."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.auth.basic import NoAuthorization
from mconet.client import ConversationRequestBuilder, model_request_from_text
from mconet.core.domain import (
    Authorization,
    ConversationInputNode,
    ConversationTaskBuilder,
    Extensions,
    Headers,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelDescriptor,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TextMessageContent,
    UriValue,
)
from mconet.integration.openai_compatible import OpenAIChatCompletionsAdapter


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target shared by the three request forms."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Structural access shared by the three request forms."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Role:
    """User role for the builder-constructed message."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Container kind for one message group."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Container kind for the task root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Mode:
    """Unary interaction mode."""

    id: OpenIdentifier


def _payload(request: ModelRequest, access: ResolvedServiceAccess) -> object:
    """Return the chat-completions JSON value for one request."""
    adapter = OpenAIChatCompletionsAdapter()
    plan = adapter.prepare_plan(request, access, _Mode(OpenIdentifier("unary")))
    built = adapter.build_request(request, plan)
    return built.payload.value


def test_text_builder_and_full_request_encode_the_same_payload() -> None:
    """Verify the three public request forms produce one protocol payload."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.example"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("example-model"),
    )
    endpoint = UriValue("https://example.test/v1", True)
    access: ServiceAccess = _Access(endpoint, NoAuthorization())
    text = "Hello"
    from_text = model_request_from_text(target, text, access)
    role: MessageRole = _Role(OpenIdentifier("message.user"))
    root_kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    current_kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.current"),
        "group",
        "container",
    )
    entry = MessageEntry(
        "message-entry",
        role,
        (TextMessageContent("text-content", text),),
    )
    messages = MessageDocument(
        "1.0",
        "input",
        MessageGroup(
            "message-root",
            root_kind,
            (MessageGroup("message-current", current_kind, (entry,)),),
        ),
    )
    task_kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    document = TaskDocument(
        "1.0",
        TaskGroupNode(
            "root",
            task_kind,
            (ConversationInputNode("input", messages),),
        ),
    )
    task = ConversationTaskBuilder(document).build()
    from_conversation_builder = (
        ConversationRequestBuilder(target, task).with_service_access(access).build()
    )
    from_model_builder = (
        ModelRequestBuilder(target, task).with_service_access(access).build()
    )
    resolved = ResolvedServiceAccess(
        endpoint,
        NoAuthorization(),
        Headers(),
        QueryParameters(),
        None,
        None,
        None,
        MappingProxyType({}),
    )
    text_payload = _payload(from_text, resolved)
    conversation_payload = _payload(from_conversation_builder, resolved)
    model_payload = _payload(from_model_builder, resolved)
    assert text_payload == conversation_payload == model_payload
    assert cast(dict[str, object], text_payload)["model"] == "example-model"
