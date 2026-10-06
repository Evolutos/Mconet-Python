"""Semantic validation for open task node tree values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.task_group_node import TaskGroupNode
from mconet.core.domain.task_node import TaskNode
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.task_relation import TaskRelation


def validate_task_node(node: TaskNode) -> TaskNode:
    """Validate one task node without recursively validating its descendants.

    Args:
        node: A concrete or custom structural task node to validate.

    Returns:
        The same node object after successful validation.

    Raises:
        TypeError: If the node or one of its fields has an invalid runtime type.
        ValueError: If identity, Kind, composition, direct children, relations, or
            JSON data violates task node semantics.

    Notes:
        Direct child identifiers are checked only against their parent and sibling
        set. Descendant semantics, document-wide ID uniqueness, relation endpoint
        resolution, and cycle detection require the complete TaskDocument and are
        intentionally deferred.
    """
    candidate = cast(object, node)
    # Structural recognition admits provider-defined task nodes while rejecting
    # partial objects before any property is read through the public protocol.
    if not isinstance(candidate, TaskNode):
        raise TypeError("node must implement TaskNode.")

    node_id = _validate_node_id(cast(object, candidate.id), "id")
    composition = _validate_kind(
        cast(object, candidate.kind),
        require_container=isinstance(candidate, TaskGroupNode),
    )
    children = _snapshot_children(cast(object, candidate.children))
    # Composition controls the current node's direct traversal shape. Child node
    # internals remain untouched until the document performs iterative traversal.
    if composition == "leaf" and children:
        raise ValueError("TaskNode leaf children must be empty.")
    _validate_direct_child_ids(children, node_id)

    relations = _snapshot_relations(cast(object, candidate.relations))
    for relation in relations:
        _validate_relation(relation)

    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_node_id(value: object, field_name: str) -> str:
    """Return one usable opaque document-local task node identifier."""
    # IDs remain case-sensitive and are never trimmed or parsed as open Kind
    # identifiers. Only absence and all-whitespace values are unusable as keys.
    if not isinstance(value, str):
        raise TypeError(f"TaskNode {field_name} must be a string.")
    if not value or value.isspace():
        raise ValueError(f"TaskNode {field_name} must not be empty or whitespace.")
    return value


def _validate_kind(value: object, *, require_container: bool) -> str:
    """Validate one open task Kind and return its composition value."""
    # Structural recognition preserves provider-defined Kind implementations and
    # still guarantees both identity and tree composition properties are present.
    if not isinstance(value, TaskNodeKind):
        raise TypeError("TaskNode kind must implement TaskNodeKind.")

    identifier = cast(object, value.id)
    composition = cast(object, value.composition)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("TaskNode kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)

    if not isinstance(composition, str):
        raise TypeError("TaskNode kind composition must be a string.")
    if composition not in ("leaf", "container"):
        raise ValueError("TaskNode kind composition must be leaf or container.")
    # The concrete group exists only to model an ordered container. Other open
    # TaskNode implementations may validly choose either structural mode.
    if require_container and composition != "container":
        raise ValueError("TaskGroupNode kind composition must be container.")
    return composition


def _snapshot_children(value: object) -> tuple[TaskNode, ...]:
    """Snapshot an ordered sequence containing only TaskNode values."""
    # Open implementations may expose mutable sequences, so validation owns one
    # stable snapshot and explicitly rejects string-like pseudo-sequences.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("TaskNode children must be a sequence.")
    snapshot = tuple(cast(Sequence[object], value))
    if any(not isinstance(child, TaskNode) for child in snapshot):
        raise TypeError("TaskNode children must contain TaskNode values.")
    return cast(tuple[TaskNode, ...], snapshot)


def _validate_direct_child_ids(children: tuple[TaskNode, ...], node_id: str) -> None:
    """Require usable, non-colliding IDs across one direct child sequence."""
    child_ids: set[str] = set()
    for child in children:
        child_id = _validate_node_id(cast(object, child.id), "child id")
        # Parent and direct children already share the same document namespace;
        # reject local collisions before whole-tree indexing repeats the check.
        if child_id == node_id:
            raise ValueError("TaskNode child id must differ from parent id.")
        if child_id in child_ids:
            raise ValueError("TaskNode direct child ids must be unique.")
        child_ids.add(child_id)


def _snapshot_relations(value: object) -> tuple[TaskRelation, ...]:
    """Snapshot an ordered sequence containing only TaskRelation values."""
    # A stable snapshot prevents caller mutation from changing the relation set
    # while each value is checked; endpoint lookup remains document-owned.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("TaskNode relations must be a sequence.")
    snapshot = tuple(cast(Sequence[object], value))
    if any(not isinstance(relation, TaskRelation) for relation in snapshot):
        raise TypeError("TaskNode relations must contain TaskRelation values.")
    return cast(tuple[TaskRelation, ...], snapshot)


def _validate_relation(relation: TaskRelation) -> None:
    """Validate portable relation fields without resolving either endpoint."""
    source = cast(object, relation.source)
    target = cast(object, relation.target)
    relation_type = cast(object, relation.type)
    # Endpoints are independent opaque node IDs. Both must be usable, but their
    # existence and any self-reference policy need the complete document index.
    if not isinstance(source, str):
        raise TypeError("TaskRelation source must be a string.")
    if not source or source.isspace():
        raise ValueError("TaskRelation source must not be empty or whitespace.")
    if not isinstance(target, str):
        raise TypeError("TaskRelation target must be a string.")
    if not target or target.isspace():
        raise ValueError("TaskRelation target must not be empty or whitespace.")

    if not isinstance(relation_type, OpenIdentifier):
        raise TypeError("TaskRelation type must be an OpenIdentifier.")
    validate_open_identifier(relation_type)
    _validate_json_mapping(cast(object, relation.metadata), "relation metadata")


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    # Public channels accept any Mapping implementation, while portable JSON
    # object keys remain strings for every language and producer.
    if not isinstance(value, Mapping):
        raise TypeError(f"TaskNode {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"TaskNode {field_name} keys must be strings.")

    # Validate values independently because a general Mapping need not itself be
    # one of the concrete dict branches accepted by the recursive validator.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
