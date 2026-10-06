"""Field, ownership, and leaf-semantics tests for MessageEntry values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageElement,
    MessageEntry,
    MessageRelation,
    MessageRole,
    OpenIdentifier,
    TextMessageContent,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for each structural role fixture."""
    # A fresh dictionary prevents one fixture mutation from changing another
    # role while still satisfying the public read-only mapping annotation.
    return {}


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural role without SDK inheritance."""

    id: OpenIdentifier
    """Open role identifier retained exactly by the entry."""

    semantic: str | None = None
    """Optional producer description of the role meaning."""

    raw_value: str | None = None
    """Optional original provider spelling of the role."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields retained without interpretation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep the exception boundary narrow so unexpected success or a different
    # failure type cannot be hidden by broad test control flow.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Crossing the static read-only boundary proves the runtime mapping proxy
    # enforces the same ownership guarantee exposed by the public annotation.
    mapping["changed"] = True


def _mutate_kind_id(entry: MessageEntry) -> None:
    """Attempt to replace the fixed Kind ID through the lowest-level setter."""
    # object.__setattr__ bypasses ordinary frozen dataclass guards. Requiring it
    # to fail proves the shared Kind view has no writable storage at all.
    object.__setattr__(entry.kind, "id", OpenIdentifier("vendor.changed"))


def _user_role() -> MessageRole:
    """Return the complete user-role fixture shared by entry tests."""
    # Structural typing keeps MessageEntry independent of a concrete standard
    # role class while the stable fixture makes assertions concise and explicit.
    return _Role(OpenIdentifier("message.user"))


def test_message_entry_is_a_fixed_leaf_with_ordered_content() -> None:
    """Verify role, content order, and fixed element projections are explicit."""
    first = TextMessageContent("content-1", "Hello")
    second = TextMessageContent("content-2", "world")
    role = _user_role()
    entry = MessageEntry("entry-1", role, (first, second))
    element: MessageElement = entry

    # Content order is independent from tree traversal. The concrete entry fills
    # the complete MessageElement surface without exposing payloads as children.
    assert isinstance(entry, MessageElement)
    assert element.id == "entry-1"
    assert entry.role is role
    assert entry.content == (first, second)
    assert entry.kind.id == OpenIdentifier("message.entry")
    assert entry.kind.category == "entry"
    assert entry.kind.composition == "leaf"
    assert entry.name is None
    assert entry.attributes == {}
    assert entry.value is None
    assert entry.sub_elements == ()
    assert entry.relations == ()
    assert entry.metadata == {}
    assert entry.extensions == {}

    # Even a low-level dynamic mutation cannot corrupt the Kind shared by this
    # or any later entry because the view exposes properties without storage.
    _assert_raises(AttributeError, lambda: _mutate_kind_id(entry), "has no setter")
    assert entry.kind.id == OpenIdentifier("message.entry")


def test_message_entry_preserves_relations_and_snapshots_json_membership() -> None:
    """Verify ordered relations and caller-owned mapping membership are isolated."""
    first_relation = MessageRelation(
        "entry-1", "source-1", OpenIdentifier("message.cites")
    )
    second_relation = MessageRelation(
        "entry-1", "source-2", OpenIdentifier("vendor.supports")
    )
    metadata: dict[str, JsonValue] = {"turn": 1}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    entry = MessageEntry(
        "entry-1",
        _user_role(),
        (TextMessageContent("content-1", "answer"),),
        relations=(first_relation, second_relation),
        metadata=metadata,
        extensions=extensions,
    )

    # Caller mutations cannot replace membership in the frozen entry, relations
    # retain exact declaration order, and public mappings reject direct writes.
    metadata["turn"] = 2
    extensions["other"] = False
    assert entry.relations == (first_relation, second_relation)
    assert entry.metadata == {"turn": 1}
    assert entry.extensions == {"vendorField": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: entry.__setattr__("id", "changed"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], entry.metadata)),
        "does not support item assignment",
    )


def test_message_entry_constructor_excludes_fixed_and_unrelated_fields() -> None:
    """Verify callers cannot override leaf semantics or add task parameters."""
    parameters = tuple(inspect.signature(MessageEntry).parameters)

    # Fixed MessageElement projections are properties, not constructor inputs;
    # task configuration and protocol access data remain outside MessageEntry.
    assert parameters == (
        "id",
        "role",
        "content",
        "relations",
        "metadata",
        "extensions",
    )
    assert "kind" not in parameters
    assert "value" not in parameters
    assert "sub_elements" not in parameters
    assert "temperature" not in parameters
    assert "authorization" not in parameters
    assert "endpoint" not in parameters


def test_message_entry_definition_defers_semantic_validation() -> None:
    """Verify empty content and malformed role identity remain validator concerns."""
    role = _Role(OpenIdentifier(" INVALID ROLE "))
    entry = MessageEntry("", role, ())

    # The value definition preserves source data without silently normalizing it.
    # A later validator owns non-empty content, ID, and role syntax failures.
    assert entry.id == ""
    assert entry.role is role
    assert entry.content == ()
    assert entry.sub_elements == ()


def test_message_entry_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass immutable structural field contracts."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteRole:
        """Expose role identity only to exercise full protocol recognition."""

        id: OpenIdentifier
        """Role identity without required optional and extension properties."""

    role = _user_role()
    content: MessageContent = TextMessageContent("content-1", "Hello")
    relation = MessageRelation("entry-1", "other", OpenIdentifier("message.links"))

    # Each failure is attributed to its own storage boundary. Semantic concerns
    # such as empty tuples or unresolved relation endpoints are not checked here.
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: MessageEntry(cast(str, 1), role, (content,)),
            "id must be a string",
        ),
        (
            lambda: MessageEntry(
                "entry-1",
                cast(MessageRole, _IncompleteRole(OpenIdentifier("message.user"))),
                (content,),
            ),
            "role must implement MessageRole",
        ),
        (
            lambda: MessageEntry(
                "entry-1", role, cast(tuple[MessageContent, ...], [content])
            ),
            "content must be a tuple",
        ),
        (
            lambda: MessageEntry(
                "entry-1", role, cast(tuple[MessageContent, ...], ("text",))
            ),
            "content must contain MessageContent values",
        ),
        (
            lambda: MessageEntry(
                "entry-1",
                role,
                (content,),
                relations=cast(tuple[MessageRelation, ...], [relation]),
            ),
            "relations must be a tuple",
        ),
        (
            lambda: MessageEntry(
                "entry-1",
                role,
                (content,),
                relations=cast(tuple[MessageRelation, ...], ("relation",)),
            ),
            "relations must contain MessageRelation values",
        ),
        (
            lambda: MessageEntry(
                "entry-1", role, (content,), metadata=cast(Extensions, [])
            ),
            "metadata must be a mapping",
        ),
        (
            lambda: MessageEntry(
                "entry-1", role, (content,), extensions=cast(Extensions, {1: True})
            ),
            "extensions keys must be strings",
        ),
    )
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
