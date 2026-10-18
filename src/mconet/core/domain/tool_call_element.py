"""Leaf message element carrying one model tool call."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_element_value import MessageElementValue
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.open_identifier import OpenIdentifier

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_TOOL_CALL_KIND_ID = OpenIdentifier("message.tool_call")


class _ToolCallKind:
    """Expose the fixed classification of a tool-call leaf."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard tool-call kind identifier."""
        # The identifier is immutable and this view has no writable storage, so
        # every access can share the same value.
        return _TOOL_CALL_KIND_ID

    @property
    def category(self) -> str:
        """Return the category that groups tool-call and tool-result leaves."""
        # The category is explicit rather than inferred from the identifier so
        # it satisfies the independent MessageElementKind contract field.
        return "tool"

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the leaf composition fixed for a tool call."""
        # A tool call is one invocation. It does not contain further messages.
        return "leaf"


_TOOL_CALL_KIND: MessageElementKind = _ToolCallKind()


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by tool-call defaults."""
    # The mapping has no nested values and rejects mutation, so sharing it keeps
    # the default allocation-free without exposing writable state.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ToolCallElement:
    """Carry one function call requested by the model.

    The element kind is always ``message.tool_call``. ``id`` is the
    document-local element identity. ``call_id`` is the invocation identity the
    service assigned and that a later tool result must cite. ``name`` is the
    function name. ``arguments`` keeps the service's argument text exactly,
    including a JSON object that has not yet been parsed.

    Place the element immediately after the assistant :class:`MessageEntry`
    it belongs to. A protocol adapter groups that run into one assistant
    message.
    """

    id: str
    """Stable element identifier local to the enclosing message document."""

    call_id: str
    """Invocation identity cited by the matching tool result."""

    name: str
    """Function name the model asked to call."""

    arguments: str
    """Argument text exactly as the model produced it."""

    call_type: str = "function"
    """Call type. The chat protocol uses ``function``."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only members the service sent outside the frozen call shape."""

    def __post_init__(self) -> None:
        """Require string storage and detach extension membership."""
        # Every identity and payload field is text. Blank call ids and names
        # stay constructible so document validation can report them as value
        # errors. Argument text may be empty.
        for field_name in ("id", "call_id", "name", "arguments", "call_type"):
            value = cast(object, getattr(self, field_name))
            if not isinstance(value, str):
                raise TypeError(f"ToolCallElement {field_name} must be a string.")
        # Extensions are members a response carried outside the frozen shape.
        # Copying membership keeps a later edit of the source from changing
        # a call that a document already stored.
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions),
        )

    @property
    def kind(self) -> MessageElementKind:
        """Return the fixed ``message.tool_call`` leaf classification."""
        # The kind object has no instance storage, so every call shares one
        # classification without letting a caller change later observations.
        return _TOOL_CALL_KIND

    @property
    def attributes(self) -> Extensions:
        """Return an empty attribute mapping; the call uses explicit fields."""
        # Call data uses explicit fields. A parallel attribute mapping would
        # be a second channel for the same facts.
        return _EMPTY_EXTENSIONS

    @property
    def value(self) -> MessageElementValue:
        """Return the call as a JSON object for generic element readers."""
        # Generic document walks can read the call without importing this type.
        # The object is rebuilt so a caller cannot change the frozen element.
        return {
            "arguments": self.arguments,
            "id": self.call_id,
            "name": self.name,
            "type": self.call_type,
        }

    @property
    def sub_elements(self) -> tuple[()]:
        """Return the permanently empty child sequence of this leaf."""
        # Composition is leaf, so message-tree traversal must not find children
        # on a tool call.
        return ()

    @property
    def relations(self) -> tuple[MessageRelation, ...]:
        """Return no relations; a tool call does not point at other elements."""
        # The call id is the link a result cites. A relation would duplicate
        # that link inside the message tree.
        return ()

    @property
    def metadata(self) -> Extensions:
        """Return an empty metadata mapping."""
        # Extra service members live in extensions. Metadata stays empty so the
        # two maps do not split one payload.
        return _EMPTY_EXTENSIONS


def _snapshot_mapping(value: Extensions) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Mapping accepts a read-only view while rejecting a sequence, which
    # cannot represent JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError("ToolCallElement extensions must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ToolCallElement extensions keys must be strings.")
    # Share the empty mapping. It has no nested values and cannot be mutated.
    if not source:
        return _EMPTY_EXTENSIONS
    # Copy top-level membership and defer recursive JSON checks. The values
    # were already accepted when the response was decoded.
    return MappingProxyType(dict(cast(Mapping[str, JsonValue], source)))
