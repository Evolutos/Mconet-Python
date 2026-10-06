"""Supported message-content scope validation for complete documents."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_document_validation import validate_message_document
from mconet.core.domain.message_element import MessageElement
from mconet.core.domain.message_entry import MessageEntry
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.text_message_content import TextMessageContent

_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_VALIDATION_PHASE = InteractionPhase(OpenIdentifier("validation"))
_UNSUPPORTED_MESSAGE_CONTENT_CODE = "unsupported_message_content"
_UNSUPPORTED_MESSAGE_CONTENT_MESSAGE = "Only TextMessageContent is supported."


def validate_text_message_content_scope(
    document: MessageDocument,
) -> MessageDocument:
    """Require every entry in a valid message document to contain only text.

    Args:
        document: The complete immutable message tree to inspect.

    Returns:
        The same document object when every content item is a validated
        :class:`TextMessageContent`.

    Raises:
        TypeError: If the document or a dynamically changed tree field has an
            invalid runtime type.
        ValueError: If the document violates its domain contract.
        ModelInteractionError: If any entry contains a non-text content value;
            its stable code is ``unsupported_message_content``.

    Notes:
        The domain remains open to future MessageContent implementations. This
        separate execution-scope gate rejects unsupported values before protocol
        adaptation or transport I/O without changing or discarding them.
    """
    # Full domain validation runs first so malformed identity, tree, role, text,
    # relation, and JSON data cannot be misreported as a support-policy failure.
    validated = validate_message_document(document)
    pending: list[MessageElement] = [validated.root]

    # Iterative preorder traversal avoids Python recursion limits for deeply
    # nested provider containers and preserves the first unsupported item in
    # producer order as the deterministic failure point.
    while pending:
        element = pending.pop()
        if isinstance(element, MessageEntry):
            for content in element.content:
                # Nominal concrete recognition is intentional: an unknown value
                # cannot claim support merely by returning the content.text Kind.
                if not isinstance(content, TextMessageContent):
                    raise _unsupported_message_content_error()
            continue

        # Domain validation already checked the tree, but open structural values
        # can expose mutable Sequences. Snapshot and narrow again before the
        # second traversal so a concurrent mutation cannot inject invalid nodes.
        children = _snapshot_children(cast(object, element.sub_elements))
        pending.extend(reversed(children))

    return validated


def _snapshot_children(value: object) -> tuple[MessageElement, ...]:
    """Return a stable tuple of message elements from an open child sequence."""
    # Strings and binary buffers are Sequences in Python but can never represent
    # element membership, so reject them before making the traversal snapshot.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("MessageElement sub_elements must be a sequence.")

    snapshot = tuple(cast(Sequence[object], value))
    # Recheck every member because a mutable sequence may have changed after the
    # complete document validator released its earlier snapshot.
    if any(not isinstance(child, MessageElement) for child in snapshot):
        raise TypeError(
            "MessageElement sub_elements must contain MessageElement values."
        )
    return cast(tuple[MessageElement, ...], snapshot)


def _unsupported_message_content_error() -> ModelInteractionError:
    """Create the normalized failure for one unsupported content value."""
    # The fixed message deliberately omits content ID, Kind, metadata, and
    # extension data so untrusted producer values cannot enter logs via errors.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_VALIDATION_PHASE,
        code=_UNSUPPORTED_MESSAGE_CONTENT_CODE,
        message=_UNSUPPORTED_MESSAGE_CONTENT_MESSAGE,
    )
