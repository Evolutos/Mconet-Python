"""Field, ownership, and container-semantics tests for TaskGroupNode values."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import FrozenInstanceError, dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageElement,
    MessageElementKind,
    MessageGroup,
    OpenIdentifier,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
)


def _empty_extensions() -> Extensions:
    """Create independent mapping storage for each custom fixture field."""
    # Each fixture receives its own dictionary so mutation cannot cross node or
    # domain boundaries while satisfying the read-only public mapping type.
    return {}


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide an open structural TaskNodeKind for group scenarios."""

    id: OpenIdentifier
    """Standard or provider-defined task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Composition retained for later semantic validation."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide a message-only Kind for cross-domain child rejection."""

    id: OpenIdentifier
    """Open message element Kind identifier."""

    category: str
    """Message-specific classification absent from TaskNodeKind."""

    composition: Literal["leaf", "container"]
    """Message tree composition supplied by the fixture."""


@dataclass(frozen=True, slots=True)
class _LeafNode:
    """Provide a custom task leaf without inheriting an SDK implementation."""

    id: str
    """Document-local node identifier."""

    kind: TaskNodeKind
    """Open task Kind describing the leaf."""

    children: Sequence[TaskNode] = ()
    """Empty child sequence retained as part of the complete protocol."""

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
    # Keeping the exception boundary narrow prevents an unrelated setup failure
    # from making a storage-shape assertion pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # The cast crosses the static read-only boundary so the test verifies that the
    # concrete MappingProxy enforces the same ownership rule at runtime.
    mapping["changed"] = True


def _leaf(node_id: str) -> _LeafNode:
    """Create one custom leaf with a stable standard task input Kind."""
    # A small factory keeps child-order tests focused on container behavior while
    # proving that concrete groups accept structural custom TaskNode values.
    return _LeafNode(node_id, _TaskKind(OpenIdentifier("task.input"), "leaf"))


def test_task_group_node_preserves_open_kind_and_ordered_children() -> None:
    """Verify container identity and exact child order remain observable."""
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    first = _leaf("input-1")
    second = _leaf("input-2")
    group = TaskGroupNode("root", kind, (first, second))
    node: TaskNode = group

    # Structural conformance needs no base-class registration. Kind identity and
    # the immutable child tuple retain the caller's exact objects and order.
    assert isinstance(group, TaskNode)
    assert node.id == "root"
    assert group.kind is kind
    assert group.kind.id == OpenIdentifier("task.root")
    assert group.kind.composition == "container"
    assert group.children == (first, second)
    assert tuple(child.id for child in group.children) == ("input-1", "input-2")
    assert group.relations == ()
    assert group.metadata == {}
    assert group.extensions == {}


def test_task_group_node_preserves_unknown_container_kind() -> None:
    """Verify provider-defined container identity remains lossless."""
    kind = _TaskKind(OpenIdentifier("vendor.review_pipeline"), "container")
    group = TaskGroupNode("reviews", kind, ())

    # Construction never maps an unknown Kind to a generic enum case or derives
    # composition from the identifier, preserving future provider semantics.
    assert group.kind is kind
    assert group.kind.id.value == "vendor.review_pipeline"
    assert group.kind.composition == "container"
    assert group.children == ()


def test_task_group_node_supports_recursive_ordered_groups() -> None:
    """Verify a group can nest another group without flattening descendants."""
    leaf = _leaf("input-1")
    section = TaskGroupNode(
        "section",
        _TaskKind(OpenIdentifier("vendor.section"), "container"),
        (leaf,),
    )
    root = TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        (section,),
    )

    # Recursive storage retains both levels and object identities exactly rather
    # than flattening a nested task group into the enclosing children tuple.
    assert root.children == (section,)
    assert root.children[0] is section
    assert section.children == (leaf,)
    assert section.children[0] is leaf


def test_task_group_node_snapshots_mappings_and_is_immutable() -> None:
    """Verify caller membership and field assignment cannot alter a group."""
    metadata: dict[str, JsonValue] = {"purpose": "input"}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    group = TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        (),
        metadata=metadata,
        extensions=extensions,
    )

    # Top-level caller changes do not leak into the group, and frozen fields plus
    # read-only proxies reject mutation through both public storage surfaces.
    metadata["purpose"] = "changed"
    extensions["other"] = False
    assert group.metadata == {"purpose": "input"}
    assert group.extensions == {"vendorField": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: group.__setattr__("id", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], group.metadata)),
        "does not support item assignment",
    )


def test_task_group_node_preserves_ordered_relations() -> None:
    """Verify relation order remains independent from child order."""
    first_relation = TaskRelation("root", "input-1", OpenIdentifier("task.contains"))
    second_relation = TaskRelation("root", "input-2", OpenIdentifier("vendor.precedes"))
    group = TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        (_leaf("input-1"), _leaf("input-2")),
        relations=(first_relation, second_relation),
    )

    # Relations are not inferred from child positions and retain their exact
    # objects and declaration sequence for later document-level resolution.
    assert group.relations == (first_relation, second_relation)
    assert group.relations[0] is first_relation
    assert group.relations[1] is second_relation


def test_task_group_node_has_no_task_specific_or_message_value_fields() -> None:
    """Verify the group remains a structural container, not a payload holder."""
    parameters = tuple(inspect.signature(TaskGroupNode).parameters)
    group = TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        (),
    )

    # The exact constructor surface contains only TaskNode fields. Task-specific
    # values belong to concrete leaves, and message payload fields never enter it.
    assert parameters == (
        "id",
        "kind",
        "children",
        "relations",
        "metadata",
        "extensions",
    )
    for field_name in ("value", "messages", "parameters", "tools", "content"):
        assert field_name not in parameters
        assert not hasattr(group, field_name)


def test_task_group_node_definition_defers_container_semantics() -> None:
    """Verify empty identity and leaf composition remain validator concerns."""
    leaf_kind = _TaskKind(OpenIdentifier("vendor.pending_group"), "leaf")
    pending_json = cast(JsonValue, ("not", "portable"))
    group = TaskGroupNode("", leaf_kind, (), metadata={"pending": pending_json})

    # Construction preserves source data without normalization. The following
    # Validator owns ID, composition, children, and recursive JSON constraints.
    assert group.id == ""
    assert group.kind is leaf_kind
    assert group.kind.composition == "leaf"
    assert group.children == ()
    assert group.metadata["pending"] is pending_json


def test_task_group_node_rejects_message_elements_as_children() -> None:
    """Verify a MessageElement cannot replace a TaskNode child."""
    message_kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.history"), "group", "container"
    )
    message_group = MessageGroup("history", message_kind, ())
    task_kind = _TaskKind(OpenIdentifier("task.root"), "container")

    # The message group deliberately lacks TaskNode.children and therefore cannot
    # enter task traversal despite both domains supporting ordered containers.
    assert isinstance(message_group, MessageElement)
    assert not isinstance(message_group, TaskNode)
    _assert_raises(
        TypeError,
        lambda: TaskGroupNode(
            "root",
            task_kind,
            cast(tuple[TaskNode, ...], (cast(MessageElement, message_group),)),
        ),
        "children must contain TaskNode values",
    )


def test_task_group_node_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass immutable field contracts."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteKind:
        """Expose only Kind identity and omit task composition."""

        id: OpenIdentifier
        """Identity alone cannot classify task tree behavior."""

    kind = _TaskKind(OpenIdentifier("task.root"), "container")
    child: TaskNode = _leaf("input-1")
    relation = TaskRelation("root", "input-1", OpenIdentifier("task.contains"))

    # Each malformed input fails at its own storage boundary. Semantic IDs,
    # composition, recursive JSON, and relation endpoints remain deferred.
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: TaskGroupNode(cast(str, 1), kind, (child,)),
            "id must be a string",
        ),
        (
            lambda: TaskGroupNode(
                "root",
                cast(TaskNodeKind, _IncompleteKind(OpenIdentifier("task.root"))),
                (child,),
            ),
            "kind must implement TaskNodeKind",
        ),
        (
            lambda: TaskGroupNode("root", kind, cast(tuple[TaskNode, ...], [child])),
            "children must be a tuple",
        ),
        (
            lambda: TaskGroupNode(
                "root", kind, cast(tuple[TaskNode, ...], (object(),))
            ),
            "children must contain TaskNode values",
        ),
        (
            lambda: TaskGroupNode(
                "root",
                kind,
                (),
                relations=cast(tuple[TaskRelation, ...], [relation]),
            ),
            "relations must be a tuple",
        ),
        (
            lambda: TaskGroupNode(
                "root",
                kind,
                (),
                relations=cast(tuple[TaskRelation, ...], (object(),)),
            ),
            "relations must contain TaskRelation values",
        ),
        (
            lambda: TaskGroupNode("root", kind, (), metadata=cast(Extensions, [])),
            "metadata must be a mapping",
        ),
        (
            lambda: TaskGroupNode(
                "root", kind, (), metadata=cast(Extensions, {1: True})
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: TaskGroupNode(
                "root", kind, (), extensions=cast(Extensions, "invalid")
            ),
            "extensions must be a mapping",
        ),
    )
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
