"""Semantic validation for one tool-call leaf."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.tool_call_element import ToolCallElement


def validate_tool_call_element(element: ToolCallElement) -> ToolCallElement:
    """Validate one tool call without attaching it to a neighboring entry.

    Args:
        element: The concrete tool-call leaf to validate.

    Returns:
        The same element after its identity, kind, and payload are valid.

    Raises:
        TypeError: If the element or one of its fields has an invalid runtime
            type.
        ValueError: If an identity or the function name is blank, or the kind
            is not ``message.tool_call``.

    Notes:
        Whether the call follows an assistant entry is a document rule. This
        function only owns the leaf. Empty argument text stays valid because a
        function may be called with no arguments.
    """
    candidate = cast(object, element)
    # Require the nominal type so an open element that only reuses the kind id
    # cannot skip the call-id and function-name rules.
    if not isinstance(candidate, ToolCallElement):
        raise TypeError("element must be a ToolCallElement.")
    _require_text(cast(object, candidate.id), "id")
    # The call id is what a later tool result cites. A blank id cannot be matched.
    _require_text(cast(object, candidate.call_id), "call_id")
    _require_text(cast(object, candidate.name), "name")
    # Arguments stay text, including an empty string. Parsing them would reject
    # a call the caller still has to answer.
    if not isinstance(cast(object, candidate.arguments), str):
        raise TypeError("ToolCallElement arguments must be a string.")
    _require_text(cast(object, candidate.call_type), "call_type")
    _validate_kind(cast(object, candidate.kind))
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _require_text(value: object, field_name: str) -> None:
    """Require one non-blank string field."""
    if not isinstance(value, str):
        raise TypeError(f"ToolCallElement {field_name} must be a string.")
    # Whitespace cannot identify a call or a function, so it is not stored as
    # a usable value even though construction still accepts any string.
    if not value or value.isspace():
        raise ValueError(
            f"ToolCallElement {field_name} must not be empty or whitespace."
        )


def _validate_kind(value: object) -> None:
    """Require the fixed tool-call kind."""
    if not isinstance(value, MessageElementKind):
        raise TypeError("ToolCallElement kind must implement MessageElementKind.")
    identifier = cast(object, value.id)
    category = cast(object, value.category)
    composition = cast(object, value.composition)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("ToolCallElement kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)
    # A concrete call cannot be reclassified. The identifier is the document's
    # only signal that this leaf is a tool call.
    if identifier.value != "message.tool_call":
        raise ValueError("ToolCallElement kind id must be message.tool_call.")
    if not isinstance(category, str):
        raise TypeError("ToolCallElement kind category must be a string.")
    if category != "tool":
        raise ValueError("ToolCallElement kind category must be tool.")
    if composition != "leaf":
        raise ValueError("ToolCallElement kind composition must be leaf.")


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    if not isinstance(value, Mapping):
        raise TypeError(f"ToolCallElement {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"ToolCallElement {field_name} keys must be strings.")
    # A general Mapping is not itself a dict, so each value is checked alone.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
