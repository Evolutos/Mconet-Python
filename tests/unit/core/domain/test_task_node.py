"""Open structural contract tests for custom TaskNode implementations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    MessageElement,
    OpenIdentifier,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
)


def _empty_extensions() -> Extensions:
    """Return a new empty JSON mapping for each custom node field."""
    # Independent dictionaries prevent one fixture's metadata or extensions
    # membership from becoming shared writable state in another fixture.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Custom task node kind used without SDK implementation inheritance."""

    id: OpenIdentifier
    """Open task node kind identifier."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition supplied by the test fixture."""


@dataclass(frozen=True, slots=True)
class _Node:
    """Custom task node proving inheritance-free protocol conformance."""

    id: str
    """Document-local task node identifier."""

    kind: TaskNodeKind
    """Open kind describing this task node."""

    children: Sequence[TaskNode] = ()
    """Ordered child task node sequence."""

    relations: Sequence[TaskRelation] = ()
    """Ordered directed task relation sequence."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown versioned task node fields."""


def _require_task_node(node: TaskNode) -> TaskNode:
    """Return a statically accepted task node without adapting it."""
    # Passing the object through this boundary proves structural typing is
    # sufficient and no SDK base class, message element, or registry is required.
    return node


def test_custom_task_node_satisfies_complete_protocol() -> None:
    """Verify a custom node exposes every task-domain field independently."""
    kind: TaskNodeKind = _Kind(OpenIdentifier("vendor.review"), "leaf")
    relation = TaskRelation(
        source="review-1",
        target="input-1",
        type=OpenIdentifier("vendor.reviews"),
        metadata={"weight": 0.8},
    )
    node = _Node(
        id="review-1",
        kind=kind,
        relations=(relation,),
        metadata={"reviewer": "quality"},
        extensions={"vendorField": {"enabled": True}},
    )

    # Runtime and static recognition inspect only the six task fields; no
    # inheritance, registration hook, message role, or MessageElement is present.
    accepted = _require_task_node(node)
    assert isinstance(node, TaskNode)
    assert accepted is node
    assert accepted.id == "review-1"
    assert accepted.kind is kind
    assert tuple(accepted.children) == ()
    assert tuple(accepted.relations) == (relation,)
    assert accepted.metadata == {"reviewer": "quality"}
    assert accepted.extensions == {"vendorField": {"enabled": True}}


def test_task_node_preserves_ordered_recursive_children() -> None:
    """Verify child order and recursive protocol typing remain observable."""
    leaf_kind: TaskNodeKind = _Kind(OpenIdentifier("task.input"), "leaf")
    container_kind: TaskNodeKind = _Kind(OpenIdentifier("task.root"), "container")
    first: TaskNode = _Node("first", leaf_kind, metadata={"position": 1})
    second: TaskNode = _Node("second", leaf_kind, metadata={"position": 2})
    container = _Node("root", container_kind, children=[first, second])

    # Sequence exposes stable producer order without constraining custom storage
    # to one Python container type, and each child retains the TaskNode protocol.
    assert isinstance(container, TaskNode)
    assert [child.id for child in container.children] == ["first", "second"]
    assert all(isinstance(child, TaskNode) for child in container.children)


def test_task_node_protocol_defers_tree_and_relation_validation() -> None:
    """Verify structural conformance does not enforce document-level semantics."""
    leaf_kind: TaskNodeKind = _Kind(OpenIdentifier("vendor.leaf"), "leaf")
    child: TaskNode = _Node("child", leaf_kind)
    unresolved = TaskRelation(
        source="parent",
        target="missing",
        type=OpenIdentifier("vendor.references"),
    )
    structurally_complete = _Node(
        "parent",
        leaf_kind,
        children=(child,),
        relations=(unresolved,),
    )

    # A runtime protocol recognizes only the complete data surface. Later node
    # and document validators reject leaf children or unresolved relation targets.
    assert isinstance(structurally_complete, TaskNode)
    assert tuple(structurally_complete.children) == (child,)
    assert tuple(structurally_complete.relations) == (unresolved,)


def test_task_node_requires_complete_task_specific_surface() -> None:
    """Verify incomplete nodes fail conformance and Task stays message-neutral."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteNode:
        """Intentionally omit all fields except task identity and kind."""

        id: str
        """Document-local candidate identifier."""

        kind: TaskNodeKind
        """Candidate task kind without remaining protocol fields."""

    kind: TaskNodeKind = _Kind(OpenIdentifier("task.input"), "leaf")
    candidate = _IncompleteNode("incomplete", kind)
    complete = _Node("complete", kind)

    # Identity and kind alone cannot replace recursive children, relations, and
    # preservation mappings. Complete TaskNode lacks MessageElement-only fields.
    assert not isinstance(candidate, TaskNode)
    assert not isinstance(cast(object, candidate.kind), TaskNode)
    assert isinstance(complete, TaskNode)
    assert not isinstance(complete, MessageElement)
