"""Wire spelling of function tools, tool calls, and tool choice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    FunctionTool,
    JsonValue,
    ToolCallElement,
)
from mconet.core.domain.function_tool import function_tool_parameters_json
from mconet.integration.openai_compatible._wire import (
    child_path,
    invalid_protocol_response,
    require_object,
    require_string,
    snapshot_extensions,
)

_STANDARD_TOOL_CHOICES = frozenset(("auto", "none", "required"))


def _no_extensions() -> Extensions:
    """Return an empty extension snapshot for a tool call built from domain data."""
    return snapshot_extensions({}, "WireToolCall")


@dataclass(frozen=True, slots=True)
class WireToolCall:
    """Hold one decoded or outbound function tool call.

    ``arguments`` stays the service's text. It is not parsed as JSON, because
    a partial or invalid argument string is still part of the call the caller
    has to answer.
    """

    id: str
    """Invocation identity assigned by the service or the caller."""

    type: str
    """Call type. The chat protocol uses ``function``."""

    name: str
    """Function name."""

    arguments: str
    """Argument text exactly as carried on the wire."""

    extensions: Extensions = field(default_factory=_no_extensions)
    """Members outside the frozen call shape, captured from a response."""

    def __post_init__(self) -> None:
        """Require string fields and freeze captured extension members."""
        # Arguments stay text even when they are not valid JSON. Parsing them
        # here would reject a call the caller still has to answer.
        for field_name in ("id", "type", "name", "arguments"):
            value = cast(object, getattr(self, field_name))
            if not isinstance(value, str):
                raise TypeError(f"WireToolCall {field_name} must be a string.")
        # Response members outside the frozen shape are captured once. A later
        # request does not write them back.
        object.__setattr__(
            self,
            "extensions",
            snapshot_extensions(self.extensions, "WireToolCall"),
        )

    def to_json(self) -> dict[str, JsonValue]:
        """Return the frozen call members in profile order."""
        # Response-only members stay off the request. The profile forbids
        # unknown request fields, and a call the SDK builds has none.
        return {
            "id": self.id,
            "type": self.type,
            "function": {"name": self.name, "arguments": self.arguments},
        }


def tool_definition_json(tool: FunctionTool) -> dict[str, JsonValue]:
    """Return one ``tools`` array element for a function tool.

    Args:
        tool: One declared function tool.

    Returns:
        An object whose ``type`` is ``function`` and whose ``function`` object
        carries the name plus any description or parameters the caller set.
    """
    function: dict[str, JsonValue] = {"name": tool.name}
    # Absent optional members are omitted. Sending null would add a member the
    # request profile does not define for this object.
    if tool.description is not None:
        function["description"] = tool.description
    # The stored schema is read-only. The request body needs a plain JSON
    # object, detached so a later edit of that object cannot change the tool.
    schema = function_tool_parameters_json(tool)
    if schema is not None:
        function["parameters"] = schema
    # Domain tools are functions, so the wrapper type is fixed rather than
    # taken from the caller.
    return {"type": "function", "function": function}


def tool_choice_json(choice: str) -> JsonValue:
    """Return the wire ``tool_choice`` for one domain choice.

    ``auto``, ``none``, and ``required`` stay strings. Any other value is a
    function name and is sent as the object form the protocol requires.

    Args:
        choice: A mode, or the exact name of one declared function.

    Returns:
        The mode string, or the named-function object.
    """
    # The three mode names are already wire values. Any other string selects
    # one function and must use the object form.
    if choice in _STANDARD_TOOL_CHOICES:
        return choice
    return {"type": "function", "function": {"name": choice}}


def tool_call_from_element(element: ToolCallElement) -> WireToolCall:
    """Return the wire call for one domain tool-call element.

    Args:
        element: One tool-call leaf attached to an assistant entry.

    Returns:
        The call whose wire ``id`` is the element's ``call_id``.
    """
    # The document id stays local. The service matches a later tool result
    # against call_id, so that value becomes the wire id.
    return WireToolCall(
        element.call_id,
        element.call_type,
        element.name,
        element.arguments,
        element.extensions,
    )


def parse_tool_calls(
    document: dict[str, JsonValue], path: str
) -> tuple[WireToolCall, ...] | None:
    """Return tool calls from a message, or ``None`` when the member is absent.

    Args:
        document: Decoded message object.
        path: JSON Pointer of the message.

    Returns:
        The calls in array order.

    Raises:
        ModelInteractionError: If ``tool_calls`` is present but not a non-empty
            array of function calls.
    """
    if "tool_calls" not in document:
        # Absence means the message has no calls. JSON null is a different
        # shape and fails the array check below.
        return None
    value = document["tool_calls"]
    calls_path = child_path(path, "tool_calls")
    if not isinstance(value, list):
        raise invalid_protocol_response(calls_path, "must be an array")
    items = cast(list[JsonValue], value)
    # An empty array is not the same as omitting the member. The profile does
    # not define a call-less tool_calls array, so it is a protocol violation.
    if not items:
        raise invalid_protocol_response(calls_path, "must not be empty")
    return tuple(
        _parse_tool_call(item, child_path(calls_path, index))
        for index, item in enumerate(items)
    )


def _parse_tool_call(value: JsonValue, path: str) -> WireToolCall:
    """Return one function call and capture members outside that shape.

    Args:
        value: One element of a ``tool_calls`` array.
        path: JSON Pointer of that element.

    Returns:
        The call with unknown members stored on ``extensions``.

    Raises:
        ModelInteractionError: If the element is not an object or a required
            string member is missing.
    """
    document = require_object(value, path)
    # id is the invocation a tool result must cite. type selects the call
    # shape; this profile reads the function object underneath it.
    call_id = require_string(document, "id", path)
    call_type = require_string(document, "type", path)
    function_path = child_path(path, "function")
    function = require_object(document.get("function"), function_path)
    name = require_string(function, "name", function_path)
    # Arguments stay a string. A partial fragment or invalid JSON is still the
    # text the caller has to answer.
    arguments = require_string(function, "arguments", function_path)
    # Members the profile does not name stay observable. They are not written
    # back onto a later request. Extra function members stay nested so they
    # are not confused with the call's own members.
    extensions: dict[str, JsonValue] = {
        key: item
        for key, item in document.items()
        if key not in {"id", "type", "function"}
    }
    function_extensions = {
        key: item for key, item in function.items() if key not in {"name", "arguments"}
    }
    if function_extensions:
        extensions["function"] = function_extensions
    return WireToolCall(call_id, call_type, name, arguments, extensions)
