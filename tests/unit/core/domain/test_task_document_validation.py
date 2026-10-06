"""Whole-tree semantic validation tests for TaskDocument values."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
    validate_task_document,
)


def _empty_extensions() -> Extensions:
    """Create independent preservation mappings for structural fixtures."""
    # Fresh dictionaries keep dynamic corruption or mutation in one document
    # scenario from changing another node's metadata or extensions.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide an open structural TaskNodeKind for tree fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined node Kind identity."""

    composition: Literal["leaf", "container"]
    """Tree composition used by whole-document traversal."""


@dataclass(frozen=True, slots=True)
class _Node:
    """Represent a provider-defined TaskNode without SDK inheritance."""

    id: str
    """Document-local node identifier."""

    kind: TaskNodeKind
    """Open task node classification."""

    children: Sequence[TaskNode] = ()
    """Ordered child node sequence."""

    relations: Sequence[TaskRelation] = ()
    """Ordered directed relation sequence."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown node fields retained for forward compatibility."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # A narrow boundary and message assertion ensure the intended document rule,
    # rather than an unrelated fixture failure, satisfies each scenario.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _leaf(
    node_id: str,
    *,
    kind_id: str = "task.input",
    relations: Sequence[TaskRelation] = (),
    metadata: Extensions | None = None,
) -> _Node:
    """Create one open leaf with caller-selected identity and relations."""
    # Explicit override points let each test vary one document invariant without
    # rebuilding unrelated Kind, collection, or preservation fields.
    return _Node(
        node_id,
        _Kind(OpenIdentifier(kind_id), "leaf"),
        relations=relations,
        metadata=metadata if metadata is not None else {},
    )


def _container(
    node_id: str,
    children: Sequence[TaskNode] = (),
    *,
    kind_id: str = "vendor.container",
    relations: Sequence[TaskRelation] = (),
) -> _Node:
    """Create one custom container with exact children and relations."""
    # Standard and unknown containers use the same structural fixture; only the
    # concrete document root has a fixed Kind identity.
    return _Node(
        node_id,
        _Kind(OpenIdentifier(kind_id), "container"),
        children=children,
        relations=relations,
    )


def _root(
    children: tuple[TaskNode, ...] = (),
    *,
    relations: tuple[TaskRelation, ...] = (),
) -> TaskGroupNode:
    """Create the standard concrete root for a task document fixture."""
    # A dedicated helper prevents unrelated tests from accidentally exercising a
    # non-root Kind while focusing on another whole-document invariant.
    return TaskGroupNode(
        "root",
        _Kind(OpenIdentifier("task.root"), "container"),
        children,
        relations=relations,
    )


def _document(
    root: TaskGroupNode | None = None,
    *,
    version: str = "1.0",
    metadata: Extensions | None = None,
    extensions: Extensions | None = None,
) -> TaskDocument:
    """Create one task document with explicit public-field overrides."""
    # None selects independent defaults without conflating an intentionally empty
    # Mapping or root with absence inside the test helper.
    return TaskDocument(
        version,
        root if root is not None else _root(),
        metadata=metadata if metadata is not None else {},
        extensions=extensions if extensions is not None else {},
    )


def _overwrite_field(value: object, field_name: str, replacement: object) -> object:
    """Replace one frozen field to emulate a corrupted dynamic boundary object."""
    # Untyped deserializers can bypass annotations and frozen guards; object-level
    # assignment creates that state without weakening production constructors.
    object.__setattr__(value, field_name, replacement)
    return value


def test_validator_accepts_multilevel_tree_and_forward_relations() -> None:
    """Verify complete traversal preserves order and resolves forward references."""
    forward = TaskRelation(
        "input-1",
        "input-2",
        OpenIdentifier("task.precedes"),
    )
    first = _leaf("input-1", relations=(forward,))
    second = _leaf("input-2", kind_id="vendor.input")
    section = _container("section", [first])
    root = _root((section, second))
    document = _document(root)

    validated = validate_task_document(document)

    # Returning the same objects and retaining every collection prove validation
    # performs no rebuilding, sorting, relation relocation, or Kind normalization.
    assert validated is document
    assert validated.root is root
    assert root.children == (section, second)
    assert section.children == [first]
    assert first.relations == (forward,)
    assert second.kind.id.value == "vendor.input"


def test_validator_accepts_future_version_unknown_kinds_and_self_relation() -> None:
    """Verify forward-compatible data and resolvable self-edges remain valid."""
    self_relation = TaskRelation(
        "custom",
        "custom",
        OpenIdentifier("vendor.self"),
    )
    custom = _leaf(
        "custom",
        kind_id="vendor.future_input",
        relations=(self_relation,),
    )
    document = _document(_root((custom,)), version="future-version")

    # Domain validation stays open to new versions and Kinds. A self-edge is
    # valid when both independent endpoints resolve to an indexed node.
    assert validate_task_document(document) is document
    assert document.version == "future-version"
    assert custom.kind.id.value == "vendor.future_input"


def test_validator_rejects_invalid_document_fields() -> None:
    """Verify nominal type, version, and concrete root fail independently."""
    _assert_raises(
        TypeError,
        lambda: validate_task_document(cast(TaskDocument, object())),
        "must be a TaskDocument",
    )
    invalid_version_type = _document()
    _overwrite_field(invalid_version_type, "version", 1)
    invalid_root = _document()
    _overwrite_field(invalid_root, "root", _leaf("not-root"))
    cases: tuple[tuple[TaskDocument, type[BaseException], str], ...] = (
        (invalid_version_type, TypeError, "version must be a string"),
        (_document(version=""), ValueError, "version must not be empty"),
        (_document(version=" "), ValueError, "version must not be empty"),
        (invalid_root, TypeError, "root must be a TaskGroupNode"),
    )

    # Dynamic corruption exercises runtime narrowing that remains necessary even
    # though normal construction already prevents these primitive shapes.
    for document, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda document=document: validate_task_document(document),
            message,
        )


def test_validator_requires_standard_root_kind() -> None:
    """Verify only task.root may identify the concrete document root."""
    wrong_root = TaskGroupNode(
        "root",
        _Kind(OpenIdentifier("vendor.root"), "container"),
        (),
    )

    # Unknown Kinds are accepted below the root, but the unique document entry
    # point has one stable cross-language semantic identity.
    _assert_raises(
        ValueError,
        lambda: validate_task_document(_document(wrong_root)),
        "root kind must be task.root",
    )


def test_validator_traverses_and_rejects_invalid_descendant_semantics() -> None:
    """Verify every descendant receives the shared TaskNode validation rules."""
    invalid_kind = cast(
        TaskNodeKind,
        _Kind(
            OpenIdentifier("vendor.invalid"),
            cast(Literal["leaf", "container"], "branch"),
        ),
    )
    invalid_child = _Node("child", invalid_kind)
    root = _root((_container("section", (invalid_child,)),))

    # Parent validation deliberately skips child internals; whole-document
    # traversal eventually visits the child and reports its invalid composition.
    _assert_raises(
        ValueError,
        lambda: validate_task_document(_document(root)),
        "composition must be leaf or container",
    )


def test_validator_enforces_document_wide_node_id_uniqueness() -> None:
    """Verify duplicates across separate branches fail one global namespace."""
    left = _container("left", (_leaf("duplicate"),))
    right = _container("right", (_leaf("duplicate"),))
    root = _root((left, right))

    # Direct children of each branch are locally unique, so failure proves the
    # document index detects collisions across otherwise independent subtrees.
    _assert_raises(
        ValueError,
        lambda: validate_task_document(_document(root)),
        "node ids must be unique",
    )


def test_validator_resolves_relations_against_complete_node_index() -> None:
    """Verify forward references pass while absent endpoints fail independently."""
    valid = TaskRelation("first", "second", OpenIdentifier("task.precedes"))
    missing_source = TaskRelation("missing", "second", OpenIdentifier("task.precedes"))
    missing_target = TaskRelation("first", "missing", OpenIdentifier("task.precedes"))

    def _with_relation(relation: TaskRelation) -> TaskDocument:
        """Build the same two-node tree with one caller-selected relation."""
        # A stable topology isolates endpoint resolution from unrelated Kind,
        # traversal, metadata, or version differences across scenarios.
        first = _leaf("first", relations=(relation,))
        second = _leaf("second")
        return _document(_root((first, second)))

    assert validate_task_document(_with_relation(valid)) is not None
    _assert_raises(
        ValueError,
        lambda: validate_task_document(_with_relation(missing_source)),
        "source must reference a task node id",
    )
    _assert_raises(
        ValueError,
        lambda: validate_task_document(_with_relation(missing_target)),
        "target must reference a task node id",
    )


def test_validator_rejects_cycles_without_recursive_overflow() -> None:
    """Verify active-ancestor tracking rejects a multi-node cycle."""
    first_children: list[TaskNode] = []
    second_children: list[TaskNode] = []
    first = _container("first", first_children)
    second = _container("second", second_children)
    first_children.append(second)
    second_children.append(first)
    document = _document(_root((first,)))

    # Distinct IDs avoid local collision diagnostics, proving the enter/leave
    # traversal state detects object ancestry rather than relying on duplicate IDs.
    _assert_raises(
        ValueError,
        lambda: validate_task_document(document),
        "tree must not contain cycles",
    )


def test_validator_handles_deep_trees_iteratively() -> None:
    """Verify valid depth beyond the Python recursion limit remains supported."""
    child: TaskNode = _leaf("leaf")
    for index in range(1_100):
        # Bottom-up immutable tuples form a deep chain without mutating nodes;
        # unique IDs isolate iterative traversal from duplicate-ID behavior.
        child = _container(f"container-{index}", (child,))
    document = _document(_root((child,)))

    assert validate_task_document(document) is document


def test_validator_rejects_invalid_document_json_channels() -> None:
    """Verify metadata and extensions contain portable recursive JSON values."""
    invalid_metadata_type = _document()
    _overwrite_field(invalid_metadata_type, "metadata", [])
    invalid_metadata_key = _document()
    _overwrite_field(invalid_metadata_key, "metadata", {1: True})
    malformed: tuple[tuple[TaskDocument, type[BaseException], str], ...] = (
        (invalid_metadata_type, TypeError, "metadata must be a mapping"),
        (invalid_metadata_key, TypeError, "metadata keys must be strings"),
        (
            _document(metadata={"invalid": cast(JsonValue, ("tuple",))}),
            TypeError,
            "JsonValue",
        ),
        (
            _document(extensions={"large": 2**53}),
            ValueError,
            "safe range",
        ),
    )

    # Each document keeps a valid tree so failures are attributable only to its
    # preservation channel and recursive portable-JSON boundary.
    for document, exception_type, message in malformed:
        _assert_raises(
            exception_type,
            lambda document=document: validate_task_document(document),
            message,
        )
