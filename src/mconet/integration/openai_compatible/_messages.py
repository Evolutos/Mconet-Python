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
    ToolCallElement,
    ToolResultElement,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)
from mconet.integration.openai_compatible._roles import wire_role
from mconet.integration.openai_compatible._tool_calls import tool_call_from_element

UNSUPPORTED_MESSAGE_CONTENT_CODE = "unsupported_message_content"
"""Stable code for request content the text protocol cannot carry."""

UNSUPPORTED_MESSAGE_ELEMENT_CODE = "unsupported_message_element"
"""Stable code for a request leaf element that is not a MessageEntry."""

EMPTY_CONVERSATION_CODE = "empty_conversation"
"""Stable code for a request document that contains no message entry."""

INVALID_TOOL_CALL_CODE = "invalid_tool_call"
"""Stable code for a tool call that is not attached to an assistant entry."""

_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_PROTOCOL_ADAPTATION = InteractionPhase(OpenIdentifier("protocol_adaptation"))
_ASSISTANT_ROLE = "assistant"


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


def wire_message(
    entry: MessageEntry,
    *,
    enforce_profile: bool,
    tool_calls: tuple[ToolCallElement, ...] = (),
) -> OpenAIChatMessageDTO:
    """Return the wire message for one request MessageEntry.

    The role is mapped first so an entry with both an unsupported role and
    unsupported content always reports the role. Text values are joined in
    tuple order with no separator, matching how ConversationTaskResult projects
    multi-part text. Tool-call elements that follow an assistant entry become
    the message's ``tool_calls``. An assistant entry whose text is empty and
    that has tool calls sends JSON null for ``content``.

    Args:
        entry: One validated request entry.
        enforce_profile: Whether unknown roles are rejected; see
            :func:`wire_role`. Content rules do not depend on the policy.
        tool_calls: Tool calls that belong to this assistant entry.

    Returns:
        The message for the entry, including tool calls when supplied.

    Raises:
        ModelInteractionError: If the role or any content value is unsupported,
            or tool calls are attached to a message that is not ``assistant``.
    """
    role = wire_role(entry.role, enforce_profile=enforce_profile)
    # Only an assistant message can carry tool_calls. Attaching them to
    # system, user, or tool would invent a request the profile does not define.
    if tool_calls and role != _ASSISTANT_ROLE:
        raise _invalid_tool_call_error()
    text = "".join(wire_text(part) for part in entry.content)
    # A tool-call message with no text uses null content. An ordinary empty
    # assistant message still sends an empty string.
    content: str | None = None if tool_calls and text == "" else text
    # None omits the member. An empty tuple would encode as [] and is not a
    # call list the profile accepts.
    calls = tuple(tool_call_from_element(element) for element in tool_calls) or None
    return OpenAIChatMessageDTO(role, content, tool_calls=calls)


def wire_messages(
    document: MessageDocument, *, enforce_profile: bool
) -> tuple[OpenAIChatMessageDTO, ...]:
    """Return the ordered wire messages for one request MessageDocument.

    Entries are visited in document preorder, so the wire order is the reading
    order of the tree. Containers such as instructions, history, and current
    groups only order their children; their own kind, name, and attributes have
    no wire spelling. Relations, metadata, and extensions are not sent because
    the request profile forbids members outside the frozen shape.

    Args:
        document: The validated input document of a conversation request.
        enforce_profile: Whether unknown roles are rejected; see
            :func:`wire_role`. Element and content rules do not depend on it.

    Returns:
        One message per entry or tool result, in preorder. Consecutive tool
        calls are folded into the preceding assistant message.

    Raises:
        ModelInteractionError: If an entry is unsupported, a leaf element is
            not a message entry, tool call, or tool result, a tool call does
            not follow an assistant entry, or the document has no message.
    """
    messages: list[OpenAIChatMessageDTO] = []
    leaves = _leaves(document)

    # Tool calls are not their own chat messages. A run of them folds into the
    # assistant entry that immediately precedes them in document order.
    index = 0
    while index < len(leaves):
        element = leaves[index]
        if isinstance(element, MessageEntry):
            calls: list[ToolCallElement] = []
            following = index + 1
            while following < len(leaves) and isinstance(
                leaves[following], ToolCallElement
            ):
                call = leaves[following]
                # The isinstance check above is the narrowing point. Repeating
                # it keeps the append independent of control-flow analysis.
                if isinstance(call, ToolCallElement):
                    calls.append(call)
                following += 1
            messages.append(
                wire_message(
                    element,
                    enforce_profile=enforce_profile,
                    tool_calls=tuple(calls),
                )
            )
            index = following
            continue
        if isinstance(element, ToolCallElement):
            # A call with no preceding assistant entry cannot be folded, and
            # sending it alone would drop the function it names.
            raise _invalid_tool_call_error()
        if isinstance(element, ToolResultElement):
            # A result is its own chat message. Folding it into the assistant
            # message would hide the tool_call_id the service uses to match it.
            messages.append(_wire_tool_result(element))
            index += 1
            continue
        raise _unsupported_element_error(element)

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


def _leaves(document: MessageDocument) -> list[MessageElement]:
    """Return document leaves in preorder, skipping container nodes."""
    leaves: list[MessageElement] = []
    pending: list[MessageElement] = [document.root]
    # Children are pushed in reverse so they are read left to right.
    while pending:
        element = pending.pop()
        if element.kind.composition == "container":
            pending.extend(reversed(tuple(element.sub_elements)))
            continue
        leaves.append(element)
    return leaves


def _wire_tool_result(element: ToolResultElement) -> OpenAIChatMessageDTO:
    """Return the tool-role message for one tool result.

    Args:
        element: One tool-result leaf from the request document.

    Returns:
        A message whose role is ``tool`` and whose ``tool_call_id`` cites the
        answered call.
    """
    # The role spelling is fixed by the protocol. It is not a MessageEntry
    # role, so it is not passed through the role mapping.
    return OpenAIChatMessageDTO(
        "tool",
        element.content,
        tool_call_id=element.tool_call_id,
        name=element.name,
    )


def _unsupported_element_error(element: MessageElement) -> ModelInteractionError:
    """Create the failure for a leaf the text protocol cannot carry."""
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE,
        phase=_PROTOCOL_ADAPTATION,
        code=UNSUPPORTED_MESSAGE_ELEMENT_CODE,
        message=(
            f"Message element kind {element.kind.id} is not supported by the "
            "OpenAI-compatible chat completions protocol."
        ),
    )


def _invalid_tool_call_error() -> ModelInteractionError:
    """Create the failure for a tool call that has no assistant message."""
    # The message names the rule and not the call, so argument text cannot
    # enter a log through this error.
    return ModelInteractionError(
        category=_INVALID_REQUEST,
        phase=_PROTOCOL_ADAPTATION,
        code=INVALID_TOOL_CALL_CODE,
        message="A tool call must follow an assistant message entry.",
    )
