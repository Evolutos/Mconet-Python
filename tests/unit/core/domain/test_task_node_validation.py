"""Semantic validation tests for open TaskNode tree values."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    OpenIdentifier,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
    validate_task_node,
)


def _empty_extensions() -> Extensions:
    """Create independent mappings for custom node defaults."""
    # Per-instance storage lets invalid dynamic fixtures mutate one field without
    # changing any other node participating in the same validation scenario.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a statically complete open task Kind."""

    id: OpenIdentifier
    """Standard or provider-defined Kind identifier."""

    composition: Literal["leaf", "container"]
    """Declared tree composition mode."""


@dataclass(frozen=True, slots=True)
class _RawKind:
    """Expose dynamically malformed Kind fields for runtime validation."""

    id: object
    """Unnarrowed candidate Kind identifier."""

    composition: object
    """Unnarrowed candidate composition value."""


@dataclass(frozen=True, slots=True)
class _Node:
    """Provide a custom structural TaskNode with configurable storage."""

    id: str
    """Document-local node identifier."""

    kind: TaskNodeKind
    """Open task Kind."""

    children: Sequence[TaskNode] = ()
    """Ordered child node sequence."""

    relations: Sequence[TaskRelation] = ()
    """Ordered relation sequence."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Non-control JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown versioned node fields."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow boundary ensures unrelated fixture construction cannot satisfy a
    # field-specific validation expectation by failing before the action runs.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _leaf(node_id: str, *, kind_id: str = "task.input") -> _Node:
    """Create one valid custom leaf with no children or relations."""
    # Keeping a single valid baseline makes each malformed scenario change only
    # the field whose diagnostic it intends to exercise.
    return _Node(node_id, _Kind(OpenIdentifier(kind_id), "leaf"))


def _container(
    node_id: str,
    children: Sequence[TaskNode] = (),
    relations: Sequence[TaskRelation] = (),
) -> _Node:
    """Create one valid custom container with caller-selected ordered edges."""
    # Custom Sequence fields exercise the open protocol path instead of relying
    # only on the immutable concrete TaskGroupNode representation.
    return _Node(
        node_id,
        _Kind(OpenIdentifier("vendor.container"), "container"),
        children=children,
        relations=relations,
    )


def _replace_relation_field(
    relation: TaskRelation,
    field_name: str,
    value: object,
) -> TaskRelation:
    """Return a deliberately corrupted relation for dynamic boundary tests."""
    # Frozen values normally prevent this state; object-level replacement models
    # deserializers or untyped callers that bypass static and constructor checks.
    object.__setattr__(relation, field_name, value)
    return relation


def test_validator_accepts_unknown_leaf_and_returns_same_node() -> None:
    """Verify open leaf identity and portable preservation mappings remain valid."""
    node = _Node(
        "review-1",
        _Kind(OpenIdentifier("vendor.review"), "leaf"),
        metadata={"priority": 2},
        extensions={"vendorField": {"enabled": True}},
    )

    # Validation preserves the producer object and unknown Kind rather than
    # normalizing either through an SDK implementation or closed registry.
    assert validate_task_node(node) is node
    assert node.kind.id.value == "vendor.review"
    assert node.metadata == {"priority": 2}
    assert node.extensions == {"vendorField": {"enabled": True}}


def test_validator_accepts_ordered_container_children_and_relations() -> None:
    """Verify mutable custom sequences are snapshotted without being rewritten."""
    first = _leaf("input-1")
    second = _leaf("input-2")
    relation = TaskRelation(
        "input-1",
        "input-2",
        OpenIdentifier("vendor.precedes"),
        metadata={"weight": 1},
    )
    children: list[TaskNode] = [first, second]
    relations = [relation]
    node = _container("root", children, relations)

    # The current pass observes stable copies internally but does not replace a
    # provider's storage or resolve endpoints before a document index exists.
    assert validate_task_node(node) is node
    assert node.children is children
    assert [child.id for child in node.children] == ["input-1", "input-2"]
    assert node.relations is relations
    assert relation.type == OpenIdentifier("vendor.precedes")


def test_validator_accepts_concrete_group_with_container_kind() -> None:
    """Verify TaskGroupNode satisfies the same shared validator contract."""
    group = TaskGroupNode(
        "root",
        _Kind(OpenIdentifier("task.root"), "container"),
        (_leaf("input-1"),),
    )

    # Concrete immutable groups follow the same open node validation path while
    # adding their fixed requirement that composition is container.
    assert validate_task_node(group) is group


def test_validator_rejects_leaf_children_and_noncontainer_group() -> None:
    """Verify composition controls children and the concrete group role."""
    leaf_with_child = _Node(
        "parent",
        _Kind(OpenIdentifier("vendor.leaf"), "leaf"),
        children=(_leaf("child"),),
    )
    group = TaskGroupNode(
        "root",
        _Kind(OpenIdentifier("vendor.pending_group"), "leaf"),
        (),
    )

    # Open leaves cannot hide descendants, and the concrete group cannot be
    # reclassified as a leaf even when its current child tuple is empty.
    _assert_raises(
        ValueError,
        lambda: validate_task_node(leaf_with_child),
        "leaf children must be empty",
    )
    _assert_raises(
        ValueError,
        lambda: validate_task_node(group),
        "TaskGroupNode kind composition must be container",
    )


def test_validator_checks_node_and_direct_child_identifiers() -> None:
    """Verify usable local IDs and direct collision rules fail independently."""
    invalid_type = _Node(
        cast(str, 1),
        _Kind(OpenIdentifier("task.input"), "leaf"),
    )
    same_as_parent = _container("same", (_leaf("same"),))
    duplicate_children = _container("root", (_leaf("duplicate"), _leaf("duplicate")))

    # Direct checks provide deterministic local errors; duplicates across deeper
    # branches remain the later TaskDocument index's responsibility.
    _assert_raises(
        TypeError,
        lambda: validate_task_node(invalid_type),
        "id must be a string",
    )
    invalid_cases: tuple[tuple[TaskNode, str], ...] = (
        (_leaf(""), "id must not be empty"),
        (_container("root", (_leaf(" "),)), "child id must not be empty"),
        (same_as_parent, "child id must differ from parent id"),
        (duplicate_children, "direct child ids must be unique"),
    )
    for node, message in invalid_cases:
        _assert_raises(
            ValueError,
            lambda node=node: validate_task_node(node),
            message,
        )


def test_validator_rejects_invalid_kind_fields() -> None:
    """Verify Kind protocol, identity syntax, and composition are distinct rules."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteKind:
        """Omit composition while retaining an apparent identity."""

        id: OpenIdentifier
        """Incomplete Kind identity."""

    malformed: tuple[tuple[TaskNodeKind, type[BaseException], str], ...] = (
        (
            cast(TaskNodeKind, _IncompleteKind(OpenIdentifier("task.input"))),
            TypeError,
            "must implement TaskNodeKind",
        ),
        (
            cast(TaskNodeKind, _RawKind("task.input", "leaf")),
            TypeError,
            "kind id must be an OpenIdentifier",
        ),
        (
            cast(TaskNodeKind, _RawKind(OpenIdentifier("Task.Input"), "leaf")),
            ValueError,
            "lowercase ASCII",
        ),
        (
            cast(TaskNodeKind, _RawKind(OpenIdentifier("task.input"), 1)),
            TypeError,
            "composition must be a string",
        ),
        (
            cast(TaskNodeKind, _RawKind(OpenIdentifier("task.input"), "branch")),
            ValueError,
            "composition must be leaf or container",
        ),
    )

    # Each malformed Kind changes one boundary so diagnostics remain stable and
    # do not depend on a standard identifier lookup table.
    for kind, exception_type, message in malformed:
        _assert_raises(
            exception_type,
            lambda kind=kind: validate_task_node(_Node("node", kind)),
            message,
        )


def test_validator_checks_children_and_relations_sequence_shapes() -> None:
    """Verify open collection fields are ordered sequences of domain values."""
    kind = _Kind(OpenIdentifier("vendor.container"), "container")
    relation = TaskRelation("root", "target", OpenIdentifier("task.references"))
    invalid_cases: tuple[tuple[TaskNode, str], ...] = (
        (
            _Node("root", kind, children=cast(Sequence[TaskNode], "invalid")),
            "children must be a sequence",
        ),
        (
            _Node("root", kind, children=cast(Sequence[TaskNode], (object(),))),
            "children must contain TaskNode values",
        ),
        (
            _Node("root", kind, relations=cast(Sequence[TaskRelation], b"invalid")),
            "relations must be a sequence",
        ),
        (
            _Node("root", kind, relations=cast(Sequence[TaskRelation], (object(),))),
            "relations must contain TaskRelation values",
        ),
    )

    # A valid relation baseline ensures collection diagnostics are not obscured
    # by endpoint or identifier validation inside the relation value itself.
    assert validate_task_node(_Node("root", kind, relations=(relation,))) is not None
    for node, message in invalid_cases:
        _assert_raises(
            TypeError,
            lambda node=node: validate_task_node(node),
            message,
        )


def test_validator_checks_relation_fields_without_resolving_endpoints() -> None:
    """Verify relation portability while leaving reference lookup to documents."""
    unresolved = TaskRelation(
        "missing-source",
        "missing-target",
        OpenIdentifier("vendor.references"),
    )
    node = _container("root", relations=(unresolved,))

    # Both endpoints are absent from this local node and still pass because only
    # TaskDocument can distinguish forward references from missing nodes.
    assert validate_task_node(node) is node

    invalid_source_type = _replace_relation_field(
        TaskRelation("source", "target", OpenIdentifier("task.references")),
        "source",
        1,
    )
    invalid_target_type = _replace_relation_field(
        TaskRelation("source", "target", OpenIdentifier("task.references")),
        "target",
        1,
    )
    invalid_type = _replace_relation_field(
        TaskRelation("source", "target", OpenIdentifier("task.references")),
        "type",
        "task.references",
    )
    invalid_metadata = _replace_relation_field(
        TaskRelation("source", "target", OpenIdentifier("task.references")),
        "metadata",
        {"invalid": float("inf")},
    )
    malformed: tuple[tuple[TaskRelation, type[BaseException], str], ...] = (
        (
            TaskRelation("", "target", OpenIdentifier("task.references")),
            ValueError,
            "source must not be empty",
        ),
        (
            TaskRelation("source", " ", OpenIdentifier("task.references")),
            ValueError,
            "target must not be empty",
        ),
        (invalid_source_type, TypeError, "source must be a string"),
        (invalid_target_type, TypeError, "target must be a string"),
        (invalid_type, TypeError, "type must be an OpenIdentifier"),
        (
            TaskRelation("source", "target", OpenIdentifier("Task.References")),
            ValueError,
            "lowercase ASCII",
        ),
        (invalid_metadata, ValueError, "finite"),
    )

    # Corrupted frozen values model an untyped deserializer bypassing constructor
    # checks, so every relation field is narrowed again at the validation boundary.
    for relation, exception_type, message in malformed:
        _assert_raises(
            exception_type,
            lambda relation=relation: validate_task_node(
                _container("root", relations=(relation,))
            ),
            message,
        )


def test_validator_rejects_invalid_preservation_mappings() -> None:
    """Verify metadata and extensions remain portable JSON objects."""
    kind = _Kind(OpenIdentifier("task.input"), "leaf")
    malformed: tuple[tuple[Extensions, Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, []), {}, TypeError, "metadata must be a mapping"),
        (
            cast(Extensions, {1: True}),
            {},
            TypeError,
            "metadata keys must be strings",
        ),
        (
            {"invalid": cast(JsonValue, ("tuple",))},
            {},
            TypeError,
            "JsonValue",
        ),
        ({}, cast(Extensions, "invalid"), TypeError, "extensions must be a mapping"),
        ({}, {"large": 2**53}, ValueError, "safe range"),
    )

    # Each case changes one preservation channel while the open Kind and tree
    # structure stay valid, isolating recursive JSON diagnostics.
    for metadata, extensions, exception_type, message in malformed:
        node = _Node("node", kind, metadata=metadata, extensions=extensions)
        _assert_raises(
            exception_type,
            lambda node=node: validate_task_node(node),
            message,
        )


def test_validator_does_not_recursively_validate_child_semantics() -> None:
    """Verify whole-tree traversal remains a TaskDocument responsibility."""
    invalid_child = _Node(
        "child",
        cast(TaskNodeKind, _RawKind(OpenIdentifier("vendor.child"), "branch")),
    )
    parent = _container("parent", (invalid_child,))

    # The parent validates its direct edge and child ID only; a later iterative
    # document traversal invokes this validator for the child and detects its Kind.
    assert validate_task_node(parent) is parent


def test_validator_rejects_objects_without_complete_task_node_surface() -> None:
    """Verify nominal-looking partial objects fail before property validation."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteNode:
        """Expose identity and Kind but omit children and preservation fields."""

        id: str
        """Candidate node identifier."""

        kind: TaskNodeKind
        """Candidate node Kind."""

    incomplete = _IncompleteNode("node", _Kind(OpenIdentifier("task.input"), "leaf"))

    # Structural recognition fails deterministically instead of raising an
    # incidental AttributeError while reading a missing protocol property.
    _assert_raises(
        TypeError,
        lambda: validate_task_node(cast(TaskNode, incomplete)),
        "must implement TaskNode",
    )
