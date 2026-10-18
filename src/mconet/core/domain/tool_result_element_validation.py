"""Semantic validation for one tool-result leaf."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.tool_result_element import ToolResultElement


def validate_tool_result_element(element: ToolResultElement) -> ToolResultElement:
    """Validate one tool result without requiring the answered call nearby.

    Args:
        element: The concrete tool-result leaf to validate.

    Returns:
        The same element after its identity and kind are valid.

    Raises:
        TypeError: If the element or one of its fields has an invalid runtime
            type.
        ValueError: If the element id, tool-call id, or a supplied function
            name is blank, or the kind is not ``message.tool_result``.

    Notes:
        Empty ``content`` stays valid. Some tools return no payload, and
        replacing it would invent a result the caller did not send. The result
        may appear without the answered call in the same document.
    """
    candidate = cast(object, element)
    if not isinstance(candidate, ToolResultElement):
        raise TypeError("element must be a ToolResultElement.")
    _require_text(cast(object, candidate.id), "id")
    # The id cites the call being answered. A blank id cannot be matched.
    _require_text(cast(object, candidate.tool_call_id), "tool_call_id")
    # Content may be empty. Only a non-string is the wrong storage kind.
    if not isinstance(cast(object, candidate.content), str):
        raise TypeError("ToolResultElement content must be a string.")
    name = cast(object, candidate.name)
    if name is not None:
        # None omits the function name. A blank name is not a function.
        _require_text(name, "name")
    _validate_kind(cast(object, candidate.kind))
    return candidate


def _require_text(value: object, field_name: str) -> None:
    """Require one non-blank string field."""
    if not isinstance(value, str):
        raise TypeError(f"ToolResultElement {field_name} must be a string.")
    if not value or value.isspace():
        raise ValueError(
            f"ToolResultElement {field_name} must not be empty or whitespace."
        )


def _validate_kind(value: object) -> None:
    """Require the fixed tool-result kind."""
    if not isinstance(value, MessageElementKind):
        raise TypeError("ToolResultElement kind must implement MessageElementKind.")
    identifier = cast(object, value.id)
    category = cast(object, value.category)
    composition = cast(object, value.composition)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("ToolResultElement kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)
    if identifier.value != "message.tool_result":
        raise ValueError("ToolResultElement kind id must be message.tool_result.")
    if not isinstance(category, str):
        raise TypeError("ToolResultElement kind category must be a string.")
    if category != "tool":
        raise ValueError("ToolResultElement kind category must be tool.")
    if composition != "leaf":
        raise ValueError("ToolResultElement kind composition must be leaf.")
