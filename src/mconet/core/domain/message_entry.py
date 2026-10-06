"""Immutable leaf element carrying one role and ordered message content."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_content import MessageContent
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.message_role import MessageRole
from mconet.core.domain.open_identifier import OpenIdentifier

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_MESSAGE_ENTRY_KIND_ID = OpenIdentifier("message.entry")


class _MessageEntryKind:
    """Expose the storage-free fixed classification of every message entry."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard message-entry kind identifier."""
        # OpenIdentifier is immutable, and this view has no writable instance
        # storage, so every access can safely share the canonical value object.
        return _MESSAGE_ENTRY_KIND_ID

    @property
    def category(self) -> str:
        """Return the stable category distinguishing entry semantics."""
        # The category is explicit rather than inferred from the identifier so
        # it satisfies the independent MessageElementKind contract field.
        return "entry"

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the leaf composition fixed for message entries."""
        # Entries carry content through their separate content tuple and must
        # never participate as containers in message-tree traversal.
        return "leaf"


_MESSAGE_ENTRY_KIND: MessageElementKind = _MessageEntryKind()


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by entry defaults."""
    # The mapping has no nested values and rejects mutation, so sharing it keeps
    # fixed empty fields allocation-free without exposing writable global state.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class MessageEntry:
    """Carry one participant role and an ordered content sequence as a leaf.

    The element kind is always ``message.entry``. Generic element fields that
    conflict with entry semantics are fixed: ``name`` is absent, ``attributes``
    is empty, ``value`` is ``None``, and ``sub_elements`` is empty. Content is a
    separate ordered tuple of :class:`MessageContent` values and never becomes
    part of message-tree traversal.

    Construction enforces immutable storage shape only. Non-empty content,
    role semantics, identifier rules, and recursive JSON validity belong to the
    dedicated message-entry validator.
    """

    id: str
    """Stable element identifier local to the enclosing message document."""

    role: MessageRole
    """Participant role associated with every content item in this entry."""

    content: tuple[MessageContent, ...]
    """Message content in exact producer-supplied order."""

    relations: tuple[MessageRelation, ...] = ()
    """Directed element relations in exact declaration order."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control metadata snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require immutable field shapes and detach mapping membership."""
        entry_id = cast(object, self.id)
        role = cast(object, self.role)
        content = cast(object, self.content)
        relations = cast(object, self.relations)

        # Keep construction limited to storage invariants. Identifier syntax and
        # role semantics need the dedicated validator and are not normalized here.
        if not isinstance(entry_id, str):
            raise TypeError("MessageEntry id must be a string.")
        if not isinstance(role, MessageRole):
            raise TypeError("MessageEntry role must implement MessageRole.")

        # Tuples make ordering stable after construction. Structural content
        # implementations remain open, while non-content objects fail early.
        if not isinstance(content, tuple):
            raise TypeError("MessageEntry content must be a tuple.")
        for item in cast(tuple[object, ...], content):
            if not isinstance(item, MessageContent):
                raise TypeError(
                    "MessageEntry content must contain MessageContent values."
                )

        # Relations use their concrete immutable value contract. Endpoint
        # existence and graph consistency require the enclosing document index.
        if not isinstance(relations, tuple):
            raise TypeError("MessageEntry relations must be a tuple.")
        for relation in cast(tuple[object, ...], relations):
            if not isinstance(relation, MessageRelation):
                raise TypeError(
                    "MessageEntry relations must contain MessageRelation values."
                )

        # Copy top-level membership so caller mutations cannot change the frozen
        # entry. Recursive JSON validation remains attributable to its validator.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )

    @property
    def kind(self) -> MessageElementKind:
        """Return the fixed ``message.entry`` leaf classification."""
        # The singleton is itself frozen, so all entries can share one canonical
        # classification without allowing callers to alter later observations.
        return _MESSAGE_ENTRY_KIND

    @property
    def name(self) -> None:
        """Return no generic element name because entries are role-addressed."""
        # A separate name would duplicate or blur role semantics, so the generic
        # optional field has one stable absent value for every entry.
        return None

    @property
    def attributes(self) -> Extensions:
        """Return an empty generic attribute mapping for this concrete type."""
        # Entry-specific data has explicit role and content fields; accepting a
        # parallel attribute payload would create a second ambiguous data channel.
        return _EMPTY_EXTENSIONS

    @property
    def value(self) -> None:
        """Return no generic element value for this concrete entry type."""
        # Payloads belong exclusively to ordered MessageContent values, keeping
        # generic element values from bypassing content mapping and validation.
        return None

    @property
    def sub_elements(self) -> tuple[()]:
        """Return the permanently empty child sequence of this leaf element."""
        # Content is intentionally not projected as children; tree traversal and
        # content mapping therefore remain separate operations.
        return ()


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Mapping accepts custom read-only implementations while rejecting values
    # that cannot represent named JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"MessageEntry {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"MessageEntry {field_name} keys must be strings.")

    # Values remain exact and uninterpreted at construction time; the dedicated
    # validator applies recursive portable-JSON and numeric constraints.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
