"""Semantic validation for complete immutable task documents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.conversation_input_node import ConversationInputNode
from mconet.core.domain.conversation_input_node_validation import (
    validate_conversation_input_node_fields,
)
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.task_document import TaskDocument
from mconet.core.domain.task_group_node import TaskGroupNode
from mconet.core.domain.task_node import TaskNode
from mconet.core.domain.task_node_validation import validate_task_node_snapshot
from mconet.core.domain.task_relation import TaskRelation


def validate_task_document(document: TaskDocument) -> TaskDocument:
    """Validate one complete task tree and all document-local references.

    Args:
        document: The concrete immutable task document to validate.

    Returns:
        The same document object after successful validation.

    Raises:
        TypeError: If the document or one of its fields has an invalid runtime
            type.
        ValueError: If version, root, tree, IDs, relations, or JSON data violates
            task document semantics.

    Notes:
        Traversal is iterative so deeply nested valid documents do not depend on
        Python's recursion limit. Relations are resolved only after the complete
        node index exists, which permits forward references independent of
        producer traversal order.
    """
    candidate = cast(object, document)
    # Require the nominal document because this validator owns version, root,
    # whole-tree identity, cycle, and reference invariants together.
    if not isinstance(candidate, TaskDocument):
        raise TypeError("document must be a TaskDocument.")

    version = cast(object, candidate.version)
    root = cast(object, candidate.root)
    # Versions remain forward-compatible opaque text; only values that cannot
    # identify any document format are rejected at this shared boundary.
    if not isinstance(version, str):
        raise TypeError("TaskDocument version must be a string.")
    if not version or version.isspace():
        raise ValueError("TaskDocument version must not be empty or whitespace.")
    if not isinstance(root, TaskGroupNode):
        raise TypeError("TaskDocument root must be a TaskGroupNode.")

    node_ids, relations = _validate_tree(root)
    # A second pass permits an edge to reference a node declared later in preorder
    # while ensuring both endpoints resolve inside this document only.
    for relation in relations:
        _resolve_relation(relation, node_ids)

    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_tree(root: TaskGroupNode) -> tuple[set[str], tuple[TaskRelation, ...]]:
    """Validate the complete tree and return its node index and relations."""
    node_ids: set[str] = set()
    relations: list[TaskRelation] = []
    active_objects: set[int] = set()
    pending: list[tuple[TaskNode, bool]] = [(root, False)]

    # Enter/leave frames detect ancestor cycles without recursive calls. Reversed
    # child pushes preserve producer preorder in the effective validation order.
    while pending:
        node, leaving = pending.pop()
        identity = id(node)
        if leaving:
            active_objects.remove(identity)
            continue
        if identity in active_objects:
            raise ValueError("TaskDocument node tree must not contain cycles.")

        active_objects.add(identity)
        pending.append((node, True))
        validated, children, node_relations = validate_task_node_snapshot(node)
        # Known concrete leaves add payload invariants after the shared node pass;
        # custom nodes remain open and require no SDK-side type registration.
        if isinstance(validated, ConversationInputNode):
            validate_conversation_input_node_fields(validated)
        _register_node_id(validated.id, node_ids)
        relations.extend(node_relations)

        # The concrete root container has one standard semantic identity; unknown
        # Kind IDs remain valid everywhere below the root for forward compatibility.
        if validated is root and validated.kind.id.value != "task.root":
            raise ValueError("TaskDocument root kind must be task.root.")

        pending.extend((child, False) for child in reversed(children))

    return node_ids, tuple(relations)


def _register_node_id(node_id: str, node_ids: set[str]) -> None:
    """Register one already validated ID in the document-wide namespace."""
    # The single global set rejects duplicates across different branches and
    # repeated object occurrences, beyond direct sibling checks owned by nodes.
    if node_id in node_ids:
        raise ValueError("TaskDocument node ids must be unique.")
    node_ids.add(node_id)


def _resolve_relation(relation: TaskRelation, node_ids: set[str]) -> None:
    """Resolve both previously validated relation endpoints against node IDs."""
    # Source and target remain independent and are never inferred from the node
    # storing the relation. Self-relations are valid when their shared ID exists.
    if relation.source not in node_ids:
        raise ValueError("TaskRelation source must reference a task node id.")
    if relation.target not in node_ids:
        raise ValueError("TaskRelation target must reference a task node id.")


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    # Document preservation channels accept any Mapping implementation, while
    # language-neutral JSON object membership remains string-keyed.
    if not isinstance(value, Mapping):
        raise TypeError(f"TaskDocument {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"TaskDocument {field_name} keys must be strings.")

    # Validate each recursive value independently without interpreting unknown
    # keys or coupling document metadata to task execution semantics.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
