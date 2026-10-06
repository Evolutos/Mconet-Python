"""Immutable task leaf carrying one conversation MessageDocument."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.task_relation import TaskRelation

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_CONVERSATION_INPUT_KIND_ID = OpenIdentifier("task.input")


class _ConversationInputKind:
    """Expose the storage-free fixed classification of conversation inputs."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard task input Kind identifier."""
        # OpenIdentifier is immutable and this view has no writable instance
        # storage, so all nodes can safely share the canonical identity value.
        return _CONVERSATION_INPUT_KIND_ID

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the leaf composition fixed for conversation inputs."""
        # MessageDocument owns its own message tree; it never becomes a sequence
        # of TaskNode children during task traversal.
        return "leaf"


_CONVERSATION_INPUT_KIND: TaskNodeKind = _ConversationInputKind()


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by node defaults."""
    # The proxy has no nested state and rejects writes, so sharing it avoids
    # allocation without exposing mutable data across independent nodes.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ConversationInputNode:
    """Carry a MessageDocument into a task as one fixed leaf node.

    The node Kind is always ``task.input`` and its TaskNode children are always
    empty. Conversation history, roles, message relations, and ordered content
    remain owned by ``messages`` rather than being projected into the task tree.
    This keeps Task and Message traversal, validation, and schema boundaries
    independent while allowing a conversation task to compose both domains.

    Construction enforces immutable storage shape only. Node identity, relation
    references, MessageDocument semantics, and recursive JSON validity belong to
    the dedicated conversation-input validator and document validators.
    """

    id: str
    """Stable node identifier local to the enclosing task document."""

    messages: MessageDocument
    """Complete conversation message document carried by this task leaf."""

    relations: tuple[TaskRelation, ...] = ()
    """Directed task relations in exact declaration order."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control node metadata membership snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field membership snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require immutable field shapes and detach mapping membership."""
        node_id = cast(object, self.id)
        messages = cast(object, self.messages)
        relations = cast(object, self.relations)

        # Preserve exact node identity and defer non-empty and uniqueness rules to
        # validators that can report them with the enclosing task context.
        if not isinstance(node_id, str):
            raise TypeError("ConversationInputNode id must be a string.")

        # Require the concrete immutable message document instead of accepting a
        # message element or arbitrary object that resembles a conversation input.
        if not isinstance(messages, MessageDocument):
            raise TypeError("ConversationInputNode messages must be a MessageDocument.")

        # Relations retain immutable declaration order. Endpoint existence needs
        # the enclosing TaskDocument node index and remains deferred.
        if not isinstance(relations, tuple):
            raise TypeError("ConversationInputNode relations must be a tuple.")
        for relation in cast(tuple[object, ...], relations):
            if not isinstance(relation, TaskRelation):
                raise TypeError(
                    "ConversationInputNode relations must contain TaskRelation values."
                )

        # Snapshot both preservation channels independently so caller membership
        # changes cannot modify the frozen node after construction.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )

    @property
    def kind(self) -> TaskNodeKind:
        """Return the fixed ``task.input`` leaf classification."""
        # The singleton has no instance storage, so sharing it cannot let one node
        # alter the Kind observed by another conversation input.
        return _CONVERSATION_INPUT_KIND

    @property
    def children(self) -> tuple[()]:
        """Return the permanently empty TaskNode child sequence."""
        # Message elements remain inside MessageDocument and are intentionally
        # excluded from task-tree traversal and node ID indexing.
        return ()


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Mapping accepts custom read-only implementations while rejecting values
    # that cannot represent named JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"ConversationInputNode {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"ConversationInputNode {field_name} keys must be strings.")

    # Values remain exact at construction time; the dedicated validator applies
    # recursive portable-JSON and numeric constraints to both channels.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
