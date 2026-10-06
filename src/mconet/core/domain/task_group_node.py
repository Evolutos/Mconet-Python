"""Immutable ordered container for task document tree nodes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.task_node import TaskNode
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.task_relation import TaskRelation

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by group defaults."""
    # The mapping contains no nested state and rejects writes, so sharing it
    # avoids allocations without creating caller-visible mutable global data.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class TaskGroupNode:
    """Group ordered task nodes under an open container Kind.

    A group implements the complete :class:`TaskNode` data surface while keeping
    children and relations in immutable tuples. Its open Kind can represent a
    standard task root or a future provider-defined container. The class has no
    generic value or task-specific payload field: concrete leaf nodes own message
    documents, parameters, tools, constraints, and other domain values.

    Construction enforces immutable storage shape only. Container composition,
    child ID rules, recursive JSON validation, relation resolution, and graph
    consistency belong to the dedicated node and document validators.
    """

    id: str
    """Stable group identifier local to the enclosing task document."""

    kind: TaskNodeKind
    """Open task node Kind whose composition is validated separately."""

    children: tuple[TaskNode, ...]
    """Child task nodes in exact producer-supplied order."""

    relations: tuple[TaskRelation, ...] = ()
    """Directed task relations in exact declaration order."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control metadata membership snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field membership snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require immutable field shapes and detach mapping membership."""
        group_id = cast(object, self.id)
        kind = cast(object, self.kind)
        children = cast(object, self.children)
        relations = cast(object, self.relations)

        # Preserve exact identifier text. Non-empty and uniqueness rules require
        # the dedicated validators and are not normalized during construction.
        if not isinstance(group_id, str):
            raise TypeError("TaskGroupNode id must be a string.")
        if not isinstance(kind, TaskNodeKind):
            raise TypeError("TaskGroupNode kind must implement TaskNodeKind.")

        # Tuple storage prevents post-construction reordering. Structural node
        # recognition admits custom TaskNode implementations without registration.
        if not isinstance(children, tuple):
            raise TypeError("TaskGroupNode children must be a tuple.")
        for child in cast(tuple[object, ...], children):
            if not isinstance(child, TaskNode):
                raise TypeError("TaskGroupNode children must contain TaskNode values.")

        # Relations are immutable values and retain declaration order. Endpoint
        # existence requires the enclosing document's complete node index.
        if not isinstance(relations, tuple):
            raise TypeError("TaskGroupNode relations must be a tuple.")
        for relation in cast(tuple[object, ...], relations):
            if not isinstance(relation, TaskRelation):
                raise TypeError(
                    "TaskGroupNode relations must contain TaskRelation values."
                )

        # Snapshot each Mapping independently so caller membership changes cannot
        # alter the frozen group after it becomes part of a task tree.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Accept the public Mapping abstraction while rejecting containers that do
    # not represent named JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"TaskGroupNode {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"TaskGroupNode {field_name} keys must be strings.")

    # Preserve values exactly and defer recursive JSON and numeric rules to the
    # node validator while isolating top-level membership from caller mutation.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
