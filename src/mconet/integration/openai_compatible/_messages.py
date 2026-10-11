"""Request mapping from a MessageDocument to OpenAI-compatible chat messages."""

from __future__ import annotations

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    MessageContent,
    MessageDocument,
    MessageElement,
    MessageEntry,
    ModelInteractionError,
    OpenIdentifier,
    TextMessageContent,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)
from mconet.integration.openai_compatible._roles import wire_role

UNSUPPORTED_MESSAGE_CONTENT_CODE = "unsupported_message_content"
"""Stable code for request content the text protocol cannot carry."""

UNSUPPORTED_MESSAGE_ELEMENT_CODE = "unsupported_message_element"
"""Stable code for a request leaf element that is not a MessageEntry."""

EMPTY_CONVERSATION_CODE = "empty_conversation"
"""Stable code for a request document that contains no message entry."""

_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_PROTOCOL_ADAPTATION = InteractionPhase(OpenIdentifier("protocol_adaptation"))


def wire_text(content: MessageContent) -> str:
    """Return the exact text of one request content value.

    Args:
        content: One content value of a request MessageEntry.

    Returns:
        ``content.text`` without trimming or Unicode normalization.

    Raises:
        ModelInteractionError: If the content is not TextMessageContent. The
            text protocol has no place for other content, and dropping it
            would silently change what the model is asked.
    """
    if isinstance(content, TextMessageContent):
        return content.text
    raise ModelInteractionError(
        category=_UNSUPPORTED_FEATURE,
        phase=_PROTOCOL_ADAPTATION,
        code=UNSUPPORTED_MESSAGE_CONTENT_CODE,
        message=(
            f"Message content kind {content.kind.id} is not supported by the "
            "OpenAI-compatible chat completions protocol."
        ),
    )


def wire_message(entry: MessageEntry) -> OpenAIChatMessageDTO:
    """Return the wire message for one request MessageEntry.

    The role is mapped first so an entry with both an unsupported role and
    unsupported content always reports the role. Text values are joined in
    tuple order with no separator, matching how ConversationTaskResult projects
    multi-part text.

    Args:
        entry: One validated request entry.

    Returns:
        The ``{"role", "content"}`` message for the entry.

    Raises:
        ModelInteractionError: If the role or any content value is unsupported.
    """
    role = wire_role(entry.role)
    return OpenAIChatMessageDTO(
        role, "".join(wire_text(part) for part in entry.content)
    )


def wire_messages(document: MessageDocument) -> tuple[OpenAIChatMessageDTO, ...]:
    """Return the ordered wire messages for one request MessageDocument.

    Entries are visited in document preorder, so the wire order is the reading
    order of the tree. Containers such as instructions, history, and current
    groups only order their children; their own kind, name, and attributes have
    no wire spelling. Relations, metadata, and extensions are not sent because
    the request profile forbids members outside the frozen shape.

    Args:
        document: The validated input document of a conversation request.

    Returns:
        One message per entry, in preorder.

    Raises:
        ModelInteractionError: If an entry is unsupported, a leaf element is
            not a MessageEntry, or the document has no entry at all.
    """
    messages: list[OpenAIChatMessageDTO] = []
    pending: list[MessageElement] = [document.root]

    # An explicit stack keeps deep, valid trees independent of Python recursion
    # depth. Children are pushed in reverse so they are read left to right.
    while pending:
        element = pending.pop()
        if isinstance(element, MessageEntry):
            messages.append(wire_message(element))
            continue
        if element.kind.composition == "container":
            pending.extend(reversed(element.sub_elements))
            continue
        # A custom leaf may carry a value the text protocol cannot express, so
        # it fails instead of being skipped.
        raise ModelInteractionError(
            category=_UNSUPPORTED_FEATURE,
            phase=_PROTOCOL_ADAPTATION,
            code=UNSUPPORTED_MESSAGE_ELEMENT_CODE,
            message=(
                f"Message element kind {element.kind.id} is not supported by the "
                "OpenAI-compatible chat completions protocol."
            ),
        )

    if not messages:
        raise ModelInteractionError(
            category=_INVALID_REQUEST,
            phase=_PROTOCOL_ADAPTATION,
            code=EMPTY_CONVERSATION_CODE,
            message=(
                "The OpenAI-compatible chat completions protocol requires at "
                "least one message entry."
            ),
        )
    return tuple(messages)
