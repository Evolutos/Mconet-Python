"""Response mapping from OpenAI-compatible wire values to domain facts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageDocument,
    MessageElement,
    MessageEntry,
    MessageGroup,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    TextMessageContent,
    TokenUsage,
    ToolCallElement,
)
from mconet.integration.openai_compatible._openai_chat_completion_choice_dto import (
    OpenAIChatCompletionChoiceDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_response_dto import (
    OpenAIChatCompletionResponseDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_usage_dto import (
    OpenAIChatCompletionUsageDTO,
)
from mconet.integration.openai_compatible._openai_chat_message_dto import (
    OpenAIChatMessageDTO,
)
from mconet.integration.openai_compatible._roles import domain_role
from mconet.integration.openai_compatible._wire import (
    child_path,
    invalid_protocol_response,
)

_OUTPUT_DOCUMENT_VERSION = "1.0"
_OUTPUT_ROOT_ID = "root"


@dataclass(frozen=True, slots=True)
class _RootKind:
    """Classify the generated output root as the standard message root."""

    id: OpenIdentifier
    category: str
    composition: Literal["leaf", "container"]


_ROOT_KIND = _RootKind(OpenIdentifier("message.root"), "group", "container")

# Only finish reasons with an exact standard meaning are mapped. Any other
# value, including future service values, keeps its text in stop_reason and
# reports the open "unknown" status rather than a guessed one.
_STATUS_BY_FINISH_REASON: MappingProxyType[str, OutputStatus] = MappingProxyType(
    {
        "stop": OutputStatus(OpenIdentifier("completed")),
        "length": OutputStatus(OpenIdentifier("incomplete")),
        "content_filter": OutputStatus(OpenIdentifier("filtered")),
        "tool_calls": OutputStatus(OpenIdentifier("requires_action")),
        "function_call": OutputStatus(OpenIdentifier("requires_action")),
    }
)
_UNKNOWN_STATUS = OutputStatus(OpenIdentifier("unknown"))


def single_choice(
    response: OpenAIChatCompletionResponseDTO,
) -> OpenAIChatCompletionChoiceDTO:
    """Return the only choice of a response.

    Requests never send ``n``, so the service is asked for exactly one choice.
    Zero choices carry no result, and several would need a selection rule the
    profile does not define, so both are protocol violations.

    Args:
        response: The decoded successful response.

    Returns:
        The single choice.

    Raises:
        ModelInteractionError: If the response does not have exactly one
            choice.
    """
    if len(response.choices) != 1:
        raise invalid_protocol_response(
            child_path("", "choices"), "must contain exactly one choice"
        )
    return response.choices[0]


def output_messages(choice: OpenAIChatCompletionChoiceDTO) -> MessageDocument:
    """Return the output MessageDocument for one choice message.

    The document has a ``message.root`` group holding one entry with one text
    content, then one ``message.tool_call`` element per call when the message
    carried ``tool_calls``. Element IDs derive from the choice index, so the
    same response always produces the same document. Null content becomes an
    empty text value. Message members outside the frozen shape, such as
    ``refusal``, are kept in the entry extensions.

    Args:
        choice: The selected response choice.

    Returns:
        A document with purpose ``output``.

    Raises:
        ModelInteractionError: If the message role is not a protocol role.
    """
    message = choice.message
    role_path = child_path(
        child_path(child_path(child_path("", "choices"), 0), "message"), "role"
    )
    entry_id = f"choice-{choice.index}"
    # Null content is an empty text segment so the entry still satisfies the
    # non-empty content rule without inventing display text.
    text = "" if message.content is None else message.content
    children: list[MessageElement] = [
        MessageEntry(
            entry_id,
            domain_role(message.role, role_path),
            (TextMessageContent(f"{entry_id}-text", text),),
            extensions=_entry_extensions(message),
        )
    ]
    if message.tool_calls is not None:
        # Calls stay siblings of the assistant entry, in array order, so a
        # later request can fold the same run back into one assistant message.
        for index, call in enumerate(message.tool_calls):
            # The element id is document-local. The service call id is stored
            # separately so a tool result can cite it.
            children.append(
                ToolCallElement(
                    f"{entry_id}-tool-{index}",
                    call.id,
                    call.name,
                    call.arguments,
                    call.type,
                    call.extensions,
                )
            )
    root = MessageGroup(_OUTPUT_ROOT_ID, _ROOT_KIND, tuple(children))
    return MessageDocument(_OUTPUT_DOCUMENT_VERSION, "output", root)


def _entry_extensions(message: OpenAIChatMessageDTO) -> Extensions:
    """Return entry extensions, including preserved name and tool-call id."""
    # Those two members are known on the wire message but have no entry field.
    # Keeping them on the entry leaves them observable without a second channel.
    preserved: dict[str, JsonValue] = {}
    if message.name is not None:
        preserved["name"] = message.name
    if message.tool_call_id is not None:
        preserved["tool_call_id"] = message.tool_call_id
    if not preserved:
        # No name or tool-call id was sent, so the captured unknown members
        # are already the complete extension snapshot.
        return message.extensions
    # Copy before updating so the message DTO's frozen extensions stay intact
    # while the entry observes both unknown members and the preserved fields.
    merged = dict(message.extensions)
    merged.update(preserved)
    return merged


def output_status(finish_reason: str) -> OutputStatus:
    """Return the standard output status for one finish reason.

    Args:
        finish_reason: Exact ``finish_reason`` text of the choice.

    Returns:
        ``completed`` for ``stop``, ``incomplete`` for ``length``, ``filtered``
        for ``content_filter``, ``requires_action`` for ``tool_calls`` and
        ``function_call``, and ``unknown`` for anything else. Matching is exact
        and case-sensitive.
    """
    return _STATUS_BY_FINISH_REASON.get(finish_reason, _UNKNOWN_STATUS)


def token_usage(usage: OpenAIChatCompletionUsageDTO | None) -> TokenUsage | None:
    """Return the domain token usage for reported wire usage.

    Each count is copied as reported. A missing count stays ``None`` and the
    total is never computed. Breakdown members stay in the extensions.

    Args:
        usage: Decoded ``usage`` object, or ``None`` when it was not sent.

    Returns:
        The token usage, or ``None`` when the service reported none.
    """
    if usage is None:
        return None
    return TokenUsage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        extensions=usage.extensions,
    )


def resolved_model(model: str | None) -> NamedModel | None:
    """Return the model the service reports it used.

    The name is copied exactly. The request target is never consulted, so an
    absent member stays absent.

    Args:
        model: Decoded ``model`` member, or ``None`` when it was not sent.

    Returns:
        The reported model, or ``None`` when the service did not report one.

    Raises:
        ModelInteractionError: If the name is empty or whitespace, which no
            valid model descriptor can carry.
    """
    if model is None:
        return None
    if not model or model.isspace():
        raise invalid_protocol_response(
            child_path("", "model"), "must not be empty or whitespace"
        )
    return NamedModel(model)
