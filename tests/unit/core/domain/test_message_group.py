"""Field, ownership, and container-semantics tests for MessageGroup values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageElement,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRelation,
    MessageRole,
    OpenIdentifier,
    TextMessageContent,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for each structural role fixture."""
    # Each role receives its own dictionary so one fixture cannot mutate another
    # through shared default state while satisfying the read-only public type.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide an open structural element Kind for group scenarios."""

    id: OpenIdentifier
    """Standard or provider-defined group Kind identifier."""

    category: str
    """Producer-defined grouping category."""

    composition: Literal["leaf", "container"]
    """Composition retained for later semantic validation."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural role for child MessageEntry values."""

    id: OpenIdentifier
    """Open role identifier."""

    semantic: str | None = None
    """Optional producer description of the role meaning."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields retained without interpretation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keeping the exception boundary narrow prevents an unrelated failure from
    # making a storage-shape test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # The cast crosses the static read-only boundary so the test can verify the
    # concrete MappingProxy enforces the same ownership rule at runtime.
    mapping["changed"] = True


def _user_role() -> MessageRole:
    """Return the shared complete user-role fixture for entry children."""
    # Structural role construction keeps group tests independent of a concrete
    # role implementation while retaining a stable standard identifier.
    return _Role(OpenIdentifier("message.user"))


def _entry(entry_id: str, text: str) -> MessageEntry:
    """Create one immutable entry child with one text content item."""
    # Distinct content IDs follow the entry IDs so child order assertions stay
    # readable without introducing a builder or document-level fixture.
    return MessageEntry(
        entry_id,
        _user_role(),
        (TextMessageContent(f"{entry_id}-content", text),),
    )


def test_message_group_preserves_open_kind_and_ordered_children() -> None:
    """Verify standard group semantics and exact child order remain observable."""
    kind: MessageElementKind = _Kind(
        OpenIdentifier("message.history"), "group", "container"
    )
    first = _entry("entry-1", "first")
    second = _entry("entry-2", "second")
    group = MessageGroup("history", kind, (first, second), name="History")
    element: MessageElement = group

    # Structural conformance needs no base-class registration. Kind identity,
    # optional name, and child tuple retain the caller's exact objects and order.
    assert isinstance(group, MessageElement)
    assert element.id == "history"
    assert group.kind is kind
    assert group.kind.id == OpenIdentifier("message.history")
    assert group.kind.category == "group"
    assert group.kind.composition == "container"
    assert group.name == "History"
    assert group.sub_elements == (first, second)
    assert tuple(child.id for child in group.sub_elements) == (
        "entry-1",
        "entry-2",
    )
    assert group.attributes == {}
    assert group.value is None
    assert group.relations == ()
    assert group.metadata == {}
    assert group.extensions == {}


def test_message_group_preserves_unknown_kind_and_generic_value() -> None:
    """Verify future container Kinds and JSON element values remain lossless."""
    kind = _Kind(OpenIdentifier("vendor.review_group"), "vendor.review", "container")
    value: JsonValue = {"layout": "stacked", "priority": 2}
    group = MessageGroup(
        "reviews",
        kind,
        (),
        attributes={"visibility": "internal"},
        value=value,
    )

    # The type definition does not close Kind identity or interpret generic JSON;
    # semantic and portable-JSON checks belong to the dedicated validator.
    assert group.kind is kind
    assert group.kind.id.value == "vendor.review_group"
    assert group.sub_elements == ()
    assert group.attributes == {"visibility": "internal"}
    assert group.value is value


def test_message_group_supports_recursive_ordered_groups() -> None:
    """Verify a container can nest another group without flattening its children."""
    entry = _entry("entry-1", "nested")
    turn = MessageGroup(
        "turn-1",
        _Kind(OpenIdentifier("message.turn"), "group", "container"),
        (entry,),
    )
    history = MessageGroup(
        "history",
        _Kind(OpenIdentifier("message.history"), "group", "container"),
        (turn,),
    )

    # Recursive storage retains both levels and their identities exactly; the
    # type never flattens a nested group into the enclosing child sequence.
    assert history.sub_elements == (turn,)
    assert history.sub_elements[0] is turn
    assert turn.sub_elements == (entry,)
    assert turn.sub_elements[0] is entry


def test_message_group_snapshots_mappings_and_is_immutable() -> None:
    """Verify mapping membership and dataclass fields cannot change after creation."""
    attributes: dict[str, JsonValue] = {"layout": "ordered"}
    metadata: dict[str, JsonValue] = {"purpose": "history"}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    group = MessageGroup(
        "history",
        _Kind(OpenIdentifier("message.history"), "group", "container"),
        (),
        attributes=attributes,
        metadata=metadata,
        extensions=extensions,
    )

    # Top-level caller changes do not leak into the group, and both frozen fields
    # and read-only proxies reject mutation through the public object surface.
    attributes["layout"] = "changed"
    metadata["purpose"] = "changed"
    extensions["other"] = False
    assert group.attributes == {"layout": "ordered"}
    assert group.metadata == {"purpose": "history"}
    assert group.extensions == {"vendorField": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: group.__setattr__("id", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], group.attributes)),
        "does not support item assignment",
    )


def test_message_group_preserves_ordered_relations() -> None:
    """Verify relation declaration order remains independent from child order."""
    first_relation = MessageRelation(
        "history", "entry-1", OpenIdentifier("message.contains")
    )
    second_relation = MessageRelation(
        "history", "entry-2", OpenIdentifier("vendor.precedes")
    )
    group = MessageGroup(
        "history",
        _Kind(OpenIdentifier("message.history"), "group", "container"),
        (_entry("entry-1", "first"), _entry("entry-2", "second")),
        relations=(first_relation, second_relation),
    )

    # Relations are not inferred from child positions and retain their exact
    # objects and declaration sequence for later document-level resolution.
    assert group.relations == (first_relation, second_relation)
    assert group.relations[0] is first_relation
    assert group.relations[1] is second_relation


def test_message_group_has_no_message_content_or_task_fields() -> None:
    """Verify the group surface remains a container rather than a payload holder."""
    parameters = tuple(inspect.signature(MessageGroup).parameters)
    group = MessageGroup(
        "history",
        _Kind(OpenIdentifier("message.history"), "group", "container"),
        (),
    )

    # Generic JsonValue is part of MessageElement, but MessageContent has no field
    # or constructor path on the group and task/access concerns remain separate.
    assert parameters == (
        "id",
        "kind",
        "sub_elements",
        "name",
        "attributes",
        "value",
        "relations",
        "metadata",
        "extensions",
    )
    assert "content" not in parameters
    assert not hasattr(group, "content")
    assert "temperature" not in parameters
    assert "authorization" not in parameters
    assert "endpoint" not in parameters


def test_message_group_definition_defers_container_semantics() -> None:
    """Verify empty children and a leaf declaration remain validator concerns."""
    leaf_kind = _Kind(OpenIdentifier("vendor.pending_group"), "group", "leaf")
    group = MessageGroup("", leaf_kind, ())

    # Construction preserves source data without normalization. The following
    # Validator owns non-empty IDs, container composition, and child ID rules.
    assert group.id == ""
    assert group.kind is leaf_kind
    assert group.kind.composition == "leaf"
    assert group.sub_elements == ()


def test_message_group_rejects_message_content_as_a_child() -> None:
    """Verify MessageContent cannot replace a MessageElement child node."""
    content = TextMessageContent("content-1", "not an element")
    kind = _Kind(OpenIdentifier("message.history"), "group", "container")

    # Text content deliberately lacks the complete element surface, keeping
    # payload mapping separate from recursive message-tree traversal.
    assert not isinstance(content, MessageElement)
    _assert_raises(
        TypeError,
        lambda: MessageGroup(
            "history",
            kind,
            cast(tuple[MessageElement, ...], (cast(MessageContent, content),)),
        ),
        "sub_elements must contain MessageElement values",
    )


def test_message_group_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass immutable structural field contracts."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteKind:
        """Expose only Kind identity and omit category and composition."""

        id: OpenIdentifier
        """Identity alone cannot classify element tree behavior."""

    kind = _Kind(OpenIdentifier("message.history"), "group", "container")
    child: MessageElement = _entry("entry-1", "first")
    relation = MessageRelation("history", "entry-1", OpenIdentifier("message.contains"))

    # Each malformed input fails at its own storage boundary. Recursive JSON,
    # composition, IDs, and relation endpoints intentionally remain deferred.
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: MessageGroup(cast(str, 1), kind, (child,)),
            "id must be a string",
        ),
        (
            lambda: MessageGroup(
                "history",
                cast(
                    MessageElementKind,
                    _IncompleteKind(OpenIdentifier("message.history")),
                ),
                (child,),
            ),
            "kind must implement MessageElementKind",
        ),
        (
            lambda: MessageGroup(
                "history", kind, cast(tuple[MessageElement, ...], [child])
            ),
            "sub_elements must be a tuple",
        ),
        (
            lambda: MessageGroup(
                "history", kind, cast(tuple[MessageElement, ...], (object(),))
            ),
            "sub_elements must contain MessageElement values",
        ),
        (
            lambda: MessageGroup("history", kind, (), name=cast(str, 1)),
            "name must be a string or None",
        ),
        (
            lambda: MessageGroup(
                "history",
                kind,
                (),
                relations=cast(tuple[MessageRelation, ...], [relation]),
            ),
            "relations must be a tuple",
        ),
        (
            lambda: MessageGroup(
                "history",
                kind,
                (),
                relations=cast(tuple[MessageRelation, ...], (object(),)),
            ),
            "relations must contain MessageRelation values",
        ),
        (
            lambda: MessageGroup("history", kind, (), attributes=cast(Extensions, [])),
            "attributes must be a mapping",
        ),
        (
            lambda: MessageGroup(
                "history", kind, (), metadata=cast(Extensions, {1: True})
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: MessageGroup(
                "history", kind, (), extensions=cast(Extensions, "invalid")
            ),
            "extensions must be a mapping",
        ),
    )
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
