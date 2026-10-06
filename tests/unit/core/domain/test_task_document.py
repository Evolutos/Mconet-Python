"""Field and ownership tests for immutable TaskDocument values."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import FrozenInstanceError, dataclass, field
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
)


def _empty_extensions() -> Extensions:
    """Create independent mappings for custom leaf fixture defaults."""
    # Separate dictionaries prevent one leaf fixture from sharing writable
    # preservation channels with another document child.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a complete structural task Kind for document fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Tree composition retained for later document validation."""


@dataclass(frozen=True, slots=True)
class _LeafNode:
    """Provide a custom task leaf for root ordering tests."""

    id: str
    """Document-local node identifier."""

    kind: TaskNodeKind
    """Open Kind describing the leaf."""

    children: Sequence[TaskNode] = ()
    """Empty recursive child sequence."""

    relations: Sequence[TaskRelation] = ()
    """Ordered directed relation sequence."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive leaf metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown leaf fields retained without interpretation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow exception boundary prevents unrelated fixture construction from
    # satisfying a storage-shape assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Crossing the static read-only boundary proves MappingProxy enforces the
    # same ownership rule at runtime rather than relying only on annotations.
    mapping["changed"] = True


def _leaf(node_id: str) -> _LeafNode:
    """Create one standard-shape task input leaf for document fixtures."""
    # A small factory keeps document tests focused on root ownership while still
    # proving the root preserves arbitrary structural TaskNode children.
    return _LeafNode(node_id, _Kind(OpenIdentifier("task.input"), "leaf"))


def _root(*children: TaskNode) -> TaskGroupNode:
    """Create a concrete task root with children in exact caller order."""
    # Children pass through unchanged so identity and ordering assertions measure
    # the document/root boundary rather than helper transformations.
    return TaskGroupNode(
        "root",
        _Kind(OpenIdentifier("task.root"), "container"),
        children,
    )


def test_task_document_preserves_version_and_root_identity() -> None:
    """Verify required fields and ordered root descendants remain exact."""
    first = _leaf("input-1")
    second = _leaf("input-2")
    root = _root(first, second)
    document = TaskDocument("1.0", root)

    # Version is independent from tree data, while the root and child sequence
    # retain the exact producer objects without copying or flattening the tree.
    assert document.version == "1.0"
    assert document.root is root
    assert document.root.children == (first, second)
    assert document.root.children[0] is first
    assert document.root.children[1] is second
    assert document.metadata == {}
    assert document.extensions == {}


def test_task_document_preserves_unknown_version_text() -> None:
    """Verify construction does not normalize future version representations."""
    document = TaskDocument("vendor-2026.preview", _root())

    # The entity is a lossless carrier; the following Validator decides whether
    # empty or otherwise unsupported version text is semantically usable.
    assert document.version == "vendor-2026.preview"


def test_task_document_snapshots_json_channels_and_is_immutable() -> None:
    """Verify mapping membership and dataclass fields cannot change after creation."""
    metadata: dict[str, JsonValue] = {"locale": "zh-CN"}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    document = TaskDocument(
        "1.0",
        _root(),
        metadata=metadata,
        extensions=extensions,
    )

    # Caller-owned top-level changes do not leak into the document, while frozen
    # fields and both mapping proxies reject writes through public storage.
    metadata["locale"] = "en"
    extensions["other"] = False
    assert document.metadata == {"locale": "zh-CN"}
    assert document.extensions == {"vendorField": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: document.__setattr__("version", "2.0"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], document.metadata)),
        "does not support item assignment",
    )


def test_task_document_constructor_contains_only_task_document_fields() -> None:
    """Verify message, access, and protocol concerns cannot enter the document."""
    parameters = tuple(inspect.signature(TaskDocument).parameters)

    # The surface mirrors the language-neutral task document exactly; descriptor,
    # artifacts, messages, credentials, transport, and payload remain elsewhere.
    assert parameters == ("version", "root", "metadata", "extensions")
    for field_name in (
        "descriptor",
        "artifacts",
        "messages",
        "authorization",
        "transport",
        "payload",
    ):
        assert field_name not in parameters


def test_task_document_definition_defers_semantic_validation() -> None:
    """Verify empty version, root identity, and recursive JSON remain validator work."""
    leaf_root = TaskGroupNode(
        "",
        _Kind(OpenIdentifier("vendor.pending_root"), "leaf"),
        (),
    )
    pending_json = cast(JsonValue, ("not", "portable"))
    document = TaskDocument("", leaf_root, metadata={"pending": pending_json})

    # Construction preserves source data without normalization. The document
    # Validator later checks version, task.root semantics, tree, and recursive JSON.
    assert document.version == ""
    assert document.root is leaf_root
    assert document.root.kind.id == OpenIdentifier("vendor.pending_root")
    assert document.root.kind.composition == "leaf"
    assert document.metadata["pending"] is pending_json


def test_task_document_requires_concrete_task_group_root() -> None:
    """Verify a structural leaf cannot masquerade as the document root."""
    leaf: TaskNode = _leaf("input-1")

    # A complete TaskNode protocol surface is insufficient: root traversal needs
    # the concrete immutable group value selected by the document contract.
    _assert_raises(
        TypeError,
        lambda: TaskDocument("1.0", cast(TaskGroupNode, leaf)),
        "root must be a TaskGroupNode",
    )


def test_task_document_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass primitive and Mapping contracts."""
    root = _root()
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: TaskDocument(cast(str, 1), root),
            "version must be a string",
        ),
        (
            lambda: TaskDocument("1.0", root, metadata=cast(Extensions, [])),
            "metadata must be a mapping",
        ),
        (
            lambda: TaskDocument("1.0", root, metadata=cast(Extensions, {1: True})),
            "metadata keys must be strings",
        ),
        (
            lambda: TaskDocument("1.0", root, extensions=cast(Extensions, "invalid")),
            "extensions must be a mapping",
        ),
        (
            lambda: TaskDocument("1.0", root, extensions=cast(Extensions, {1: True})),
            "extensions keys must be strings",
        ),
    )

    # Only storage shape is checked here; recursive JSON and semantic rules are
    # intentionally exercised by the following dedicated document Validator.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
