"""Leaf message element carrying the result of one tool call."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_element_value import MessageElementValue
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.open_identifier import OpenIdentifier

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_TOOL_RESULT_KIND_ID = OpenIdentifier("message.tool_result")


class _ToolResultKind:
    """Expose the fixed classification of a tool-result leaf."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard tool-result kind identifier."""
        # The identifier is immutable and this view has no writable storage, so
        # every access can share the same value.
        return _TOOL_RESULT_KIND_ID

    @property
    def category(self) -> str:
        """Return the category that groups tool-call and tool-result leaves."""
        # The category is explicit rather than inferred from the identifier so
        # it satisfies the independent MessageElementKind contract field.
        return "tool"

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the leaf composition fixed for a tool result."""
        # A result answers one call and does not contain further messages.
        return "leaf"


_TOOL_RESULT_KIND: MessageElementKind = _ToolResultKind()


@dataclass(frozen=True, slots=True)
class ToolResultElement:
    """Carry one tool result that answers a previous tool call.

    The element kind is always ``message.tool_result``. ``tool_call_id`` cites
    the ``call_id`` of the tool call being answered. ``content`` is the result
    text sent back to the model. ``name`` is the optional function name some
    services also require on the result message.

    A protocol adapter sends the element as its own message. It is not folded
    into the preceding assistant message.
    """

    id: str
    """Stable element identifier local to the enclosing message document."""

    tool_call_id: str
    """``call_id`` of the tool call this result answers."""

    content: str
    """Result text sent back to the model."""

    name: str | None = None
    """Optional function name paired with the result."""

    def __post_init__(self) -> None:
        """Require string storage for the result fields."""
        # The result text may be empty. The model still needs the call id
        # that this result answers, so that field uses the same string rule.
        for field_name in ("id", "tool_call_id", "content"):
            value = cast(object, getattr(self, field_name))
            if not isinstance(value, str):
                raise TypeError(f"ToolResultElement {field_name} must be a string.")
        # Name is optional. Services that do not require the function name
        # on a result leave it unset rather than storing an empty string.
        name = cast(object, self.name)
        if name is not None and not isinstance(name, str):
            raise TypeError("ToolResultElement name must be a string or None.")

    @property
    def kind(self) -> MessageElementKind:
        """Return the fixed ``message.tool_result`` leaf classification."""
        # The kind object has no instance storage, so every result shares one
        # classification without letting a caller change later observations.
        return _TOOL_RESULT_KIND

    @property
    def attributes(self) -> Extensions:
        """Return an empty attribute mapping; the result uses explicit fields."""
        # Result data uses explicit fields. A parallel attribute mapping would
        # be a second channel for the same facts.
        return _EMPTY_EXTENSIONS

    @property
    def value(self) -> MessageElementValue:
        """Return the result as a JSON object for generic element readers."""
        document: dict[str, JsonValue] = {
            "content": self.content,
            "tool_call_id": self.tool_call_id,
        }
        # A missing name is omitted so the object contains only members the
        # caller set. An empty string is a name and is kept.
        if self.name is not None:
            document["name"] = self.name
        return document

    @property
    def sub_elements(self) -> tuple[()]:
        """Return the permanently empty child sequence of this leaf."""
        # Composition is leaf, so message-tree traversal must not find children
        # on a tool result.
        return ()

    @property
    def relations(self) -> tuple[MessageRelation, ...]:
        """Return no relations; the tool call id is the only link."""
        # ``tool_call_id`` already cites the call. A relation would duplicate
        # that link inside the message tree.
        return ()

    @property
    def metadata(self) -> Extensions:
        """Return an empty metadata mapping."""
        # The result has no extra payload channel. Metadata stays empty so it
        # cannot disagree with content, call id, or name.
        return _EMPTY_EXTENSIONS

    @property
    def extensions(self) -> Extensions:
        """Return an empty extension mapping."""
        # Unknown response members are not part of a result the caller builds.
        # The mapping stays empty so a request encodes only the explicit fields.
        return _EMPTY_EXTENSIONS
