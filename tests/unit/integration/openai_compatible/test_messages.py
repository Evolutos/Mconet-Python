"""Tests for mapping request message trees to OpenAI-compatible messages."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from mconet.core.domain import (
    Extensions,
    MessageContentKind,
    MessageDocument,
    MessageElement,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRelation,
    ModelInteractionError,
    OpenIdentifier,
    TextMessageContent,
)
from mconet.integration.openai_compatible._messages import (
    EMPTY_CONVERSATION_CODE,
    UNSUPPORTED_MESSAGE_CONTENT_CODE,
    UNSUPPORTED_MESSAGE_ELEMENT_CODE,
    wire_message,
    wire_messages,
    wire_text,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for fixtures."""
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Complete MessageElementKind for fixture elements."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


@dataclass(frozen=True, slots=True)
class _Role:
    """Caller-defined role used as request input."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _ContentKind:
    """Provider-defined content kind."""

    id: OpenIdentifier


def _image_kind() -> MessageContentKind:
    """Return a non-text content kind."""
    return _ContentKind(OpenIdentifier("content.image"))


@dataclass(frozen=True, slots=True)
class _ImageContent:
    """Valid content that the text protocol cannot carry."""

    id: str
    kind: MessageContentKind = field(default_factory=_image_kind)
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _CustomLeaf:
    """Custom leaf element that is not a MessageEntry."""

    id: str
    kind: MessageElementKind = field(
        default_factory=lambda: _Kind(OpenIdentifier("vendor.note"), "note", "leaf")
    )
    name: str | None = None
    attributes: Extensions = field(default_factory=_empty_extensions)
    value: None = None
    sub_elements: tuple[MessageElement, ...] = ()
    relations: tuple[MessageRelation, ...] = ()
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _entry(entry_id: str, role_id: str, *segments: str) -> MessageEntry:
    """Create one entry whose text contents have deterministic IDs."""
    content = tuple(
        TextMessageContent(f"{entry_id}-{index}", text)
        for index, text in enumerate(segments)
    )
    return MessageEntry(entry_id, _Role(OpenIdentifier(role_id)), content)


def _group(group_id: str, *children: MessageElement) -> MessageGroup:
    """Create one ordered container group."""
    return MessageGroup(
        group_id, _Kind(OpenIdentifier("message.group"), "group", "container"), children
    )


def _document(*children: MessageElement) -> MessageDocument:
    """Create one input document whose root holds the children."""
    root = MessageGroup(
        "root", _Kind(OpenIdentifier("message.root"), "group", "container"), children
    )
    return MessageDocument("1.0", "input", root)


def test_text_content_maps_to_its_exact_text() -> None:
    """Verify text is neither trimmed nor normalized."""
    text = "  e\u0301 \u2014 \U0001f44b\n"

    assert wire_text(TextMessageContent("c", text)) == text


def test_non_text_content_is_unsupported() -> None:
    """Verify non-text content fails instead of being dropped."""
    error = _capture(lambda: wire_text(_ImageContent("image")))

    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "unsupported_feature"
    assert error.phase.id.value == "protocol_adaptation"
    assert error.code == UNSUPPORTED_MESSAGE_CONTENT_CODE
    assert error.message == (
        "Message content kind content.image is not supported by the "
        "OpenAI-compatible chat completions protocol."
    )


def test_entry_joins_text_parts_in_order_without_a_separator() -> None:
    """Verify multi-part entries become one message with exact text."""
    entry = _entry("a", "message.assistant", "Caf", "e\u0301", "", " done")

    assert wire_message(entry) == OpenAIChatMessageDTO("assistant", "Cafe\u0301 done")


def test_entry_reports_the_role_before_the_content() -> None:
    """Verify the role is checked first when both are unsupported."""
    entry = MessageEntry(
        "t", _Role(OpenIdentifier("message.tool")), (_ImageContent("image"),)
    )

    error = _capture(lambda: wire_message(entry))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_message_role"


def test_entry_with_mixed_content_is_unsupported() -> None:
    """Verify one non-text part rejects the whole entry."""
    entry = MessageEntry(
        "u",
        _Role(OpenIdentifier("message.user")),
        (TextMessageContent("t", "look"), _ImageContent("image")),
    )

    error = _capture(lambda: wire_message(entry))

    assert isinstance(error, ModelInteractionError)
    assert error.code == UNSUPPORTED_MESSAGE_CONTENT_CODE


def test_document_maps_entries_in_preorder_across_nested_groups() -> None:
    """Verify group structure only orders entries and is not sent."""
    document = _document(
        _group("instructions", _entry("s", "message.system", "Be exact.")),
        _group(
            "history",
            _entry("u1", "message.user", "Hi"),
            _group("inner", _entry("a1", "message.assistant", "Hel", "lo")),
        ),
        _entry("u2", "message.user", "Next"),
    )

    assert wire_messages(document) == (
        OpenAIChatMessageDTO("system", "Be exact."),
        OpenAIChatMessageDTO("user", "Hi"),
        OpenAIChatMessageDTO("assistant", "Hello"),
        OpenAIChatMessageDTO("user", "Next"),
    )


def test_document_rejects_a_custom_leaf_element() -> None:
    """Verify a leaf that is not an entry fails instead of being skipped."""
    document = _document(_entry("u", "message.user", "Hi"), _CustomLeaf("note"))

    error = _capture(lambda: wire_messages(document))

    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "unsupported_feature"
    assert error.phase.id.value == "protocol_adaptation"
    assert error.code == UNSUPPORTED_MESSAGE_ELEMENT_CODE
    assert error.message == (
        "Message element kind vendor.note is not supported by the "
        "OpenAI-compatible chat completions protocol."
    )


def test_document_reports_the_first_failure_in_preorder() -> None:
    """Verify failure order follows reading order, not element kind."""
    document = _document(
        _group("g", _entry("t", "message.tool", "x")), _CustomLeaf("note")
    )

    error = _capture(lambda: wire_messages(document))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_message_role"


def test_document_without_entries_is_an_invalid_request() -> None:
    """Verify a request needs at least one message."""
    for document in (_document(), _document(_group("empty"))):
        error = _capture(lambda document=document: wire_messages(document))

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "invalid_request"
        assert error.phase.id.value == "protocol_adaptation"
        assert error.code == EMPTY_CONVERSATION_CODE
