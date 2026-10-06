"""Tests for fluent construction of immutable message entries."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContent,
    MessageContentKind,
    MessageEntry,
    MessageEntryBuilder,
    MessageRelation,
    MessageRole,
    OpenIdentifier,
    TextMessageContent,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for structural role fixtures."""
    # A fresh mapping prevents one test role from sharing mutable unknown fields
    # with a role used by another independently executed builder scenario.
    return {}


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide an open structural role accepted by MessageEntryBuilder."""

    id: OpenIdentifier
    """Standard or provider-defined role identity."""

    semantic: str | None = None
    """Optional producer description of the role meaning."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _ContentKind:
    """Provide an open content Kind for a future-content builder fixture."""

    id: OpenIdentifier
    """Provider-defined content classification."""


@dataclass(frozen=True, slots=True)
class _FutureContent:
    """Represent structural content without SDK implementation inheritance."""

    id: str
    """Document-local content identifier."""

    kind: MessageContentKind
    """Open content classification retained by the entry."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown content fields retained for forward compatibility."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require one action to raise the expected type and diagnostic fragment."""
    # Keep the boundary narrow so an unrelated failure cannot satisfy a negative
    # builder test or hide an unexpected successful mutation.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _user_role() -> MessageRole:
    """Return a complete structural user role for ordinary builder scenarios."""
    # The fixture uses the open role protocol instead of an SDK-only concrete
    # standard-role class, preserving the same extensibility as production code.
    return _Role(OpenIdentifier("message.user"))


def test_builder_matches_direct_message_entry_construction() -> None:
    """Verify all builder fields produce the same value as direct construction."""
    role = _user_role()
    first = TextMessageContent("content-1", "Hello")
    second = TextMessageContent("content-2", "世界 👋")
    first_relation = MessageRelation(
        "entry-1", "entry-2", OpenIdentifier("message.precedes")
    )
    second_relation = MessageRelation(
        "entry-1", "entry-3", OpenIdentifier("vendor.supports")
    )
    metadata: Extensions = {"turn": 1, "labels": ["greeting", "unicode"]}
    extensions: Extensions = {"vendor.trace": {"enabled": True}}

    builder = MessageEntryBuilder("entry-1", role)
    returned = (
        builder.add_content(first)
        .add_content(second)
        .add_relation(first_relation)
        .add_relation(second_relation)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )
    built = builder.build()
    direct = MessageEntry(
        "entry-1",
        role,
        (first, second),
        relations=(first_relation, second_relation),
        metadata=metadata,
        extensions=extensions,
    )

    # Identity proves fluent methods operate on one builder. Dataclass equality
    # proves no field, order, role object, content object, or unknown data differs
    # from the ordinary immutable constructor result.
    assert returned is builder
    assert built == direct
    assert built is not direct
    assert built.role is role
    assert built.content == (first, second)
    assert built.relations == (first_relation, second_relation)


def test_builder_owns_state_and_each_build_returns_a_fresh_snapshot() -> None:
    """Verify caller mutations and later fluent calls cannot alter built entries."""
    metadata: dict[str, JsonValue] = {"turn": 1}
    extensions: dict[str, JsonValue] = {"vendor.mode": "initial"}
    first_content = TextMessageContent("content-1", "first")
    second_content = TextMessageContent("content-2", "second")
    relation = MessageRelation("entry-1", "entry-2", OpenIdentifier("message.precedes"))
    builder = (
        MessageEntryBuilder("entry-1", _user_role())
        .add_content(first_content)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )

    # Mapping membership is captured at the fluent boundary, not when build is
    # eventually called, so external changes cannot leak into builder state.
    metadata["turn"] = 2
    extensions["vendor.extra"] = True
    first = builder.build()

    # Later builder mutations affect only later snapshots. Tuple and mapping
    # ownership keep the first immutable result stable and independently usable.
    builder.add_content(second_content).add_relation(relation)
    second = builder.build()
    assert first is not second
    assert first.content == (first_content,)
    assert first.relations == ()
    assert first.metadata == {"turn": 1}
    assert first.extensions == {"vendor.mode": "initial"}
    assert second.content == (first_content, second_content)
    assert second.relations == (relation,)


def test_builders_never_share_default_mutable_state() -> None:
    """Verify separate builder instances own separate collections and mappings."""
    first_content = TextMessageContent("content-1", "first")
    second_content = TextMessageContent("content-2", "second")
    first_builder = MessageEntryBuilder("entry-1", _user_role()).add_content(
        first_content
    )
    second_builder = MessageEntryBuilder("entry-2", _user_role()).add_content(
        second_content
    )
    first_builder.with_metadata({"owner": "first"})

    # The second builder remains at its own defaults even after the first builder
    # mutates every relevant collection channel.
    first = first_builder.build()
    second = second_builder.build()
    assert first.content == (first_content,)
    assert second.content == (second_content,)
    assert first.metadata == {"owner": "first"}
    assert second.metadata == {}
    assert second.relations == ()
    assert second.extensions == {}


def test_builder_preserves_open_role_and_future_content() -> None:
    """Verify fluent construction does not close structural extension points."""
    role = _Role(
        OpenIdentifier("vendor.reviewer"),
        semantic="Reviews one response.",
        raw_value="Reviewer",
        extensions={"vendor.policy": "quality"},
    )
    content = _FutureContent(
        "content-1",
        _ContentKind(OpenIdentifier("vendor.rich_text")),
        metadata={"language": "zh-CN"},
        extensions={"vendor.emphasis": True},
    )

    # add_content checks only the open protocol and build delegates the same open
    # semantics as direct MessageEntry validation, retaining exact objects.
    built = MessageEntryBuilder("entry-1", role).add_content(content).build()
    assert type(built) is MessageEntry
    assert built.role is role
    assert built.content == (content,)
    assert built.content[0] is content


def test_builder_delegates_semantic_failures_to_entry_validator() -> None:
    """Verify build applies ID, role, content, and recursive JSON semantics."""
    invalid_role = _Role(OpenIdentifier(" INVALID ROLE "))
    cases: tuple[tuple[MessageEntryBuilder, type[BaseException], str], ...] = (
        (
            MessageEntryBuilder("entry-1", _user_role()),
            ValueError,
            "content must not be empty",
        ),
        (
            MessageEntryBuilder("", _user_role()).add_content(
                TextMessageContent("content-1", "text")
            ),
            ValueError,
            "id must not be empty",
        ),
        (
            MessageEntryBuilder("entry-1", invalid_role).add_content(
                TextMessageContent("content-1", "text")
            ),
            ValueError,
            "OpenIdentifier",
        ),
        (
            MessageEntryBuilder("entry-1", _user_role())
            .add_content(TextMessageContent("content-1", "text"))
            .with_metadata({"invalid": cast(JsonValue, ("tuple",))}),
            TypeError,
            "JsonValue",
        ),
    )

    # These errors originate from validate_message_entry during build, proving
    # the builder does not maintain a divergent copy of domain semantics.
    for builder, exception_type, message in cases:
        _assert_raises(exception_type, builder.build, message)


def test_builder_rejects_invalid_storage_inputs_without_partial_mutation() -> None:
    """Verify fluent boundaries reject wrong runtime shapes before state changes."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteRole:
        """Expose only identity so full MessageRole recognition must fail."""

        id: OpenIdentifier
        """Role identity without semantic, raw value, or extensions fields."""

    builder = MessageEntryBuilder("entry-1", _user_role())
    invalid_actions: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: MessageEntryBuilder(cast(str, 1), _user_role()),
            "entry_id must be a string",
        ),
        (
            lambda: MessageEntryBuilder(
                "entry-1",
                cast(MessageRole, _IncompleteRole(OpenIdentifier("message.user"))),
            ),
            "role must implement MessageRole",
        ),
        (
            lambda: builder.add_content(cast(MessageContent, object())),
            "content must implement MessageContent",
        ),
        (
            lambda: builder.add_relation(cast(MessageRelation, object())),
            "relation must be a MessageRelation",
        ),
        (
            lambda: builder.with_metadata(cast(Extensions, [])),
            "metadata must be a mapping",
        ),
        (
            lambda: builder.with_extensions(cast(Extensions, {1: True})),
            "extensions keys must be strings",
        ),
    )

    # Each operation validates before append or replacement. After all failures,
    # a normal content addition still produces an entry with no partial residue.
    for action, message in invalid_actions:
        _assert_raises(TypeError, action, message)
    content = TextMessageContent("content-1", "valid")
    built = builder.add_content(content).build()
    assert built.content == (content,)
    assert built.relations == ()
    assert built.metadata == {}
    assert built.extensions == {}


def test_builder_surface_contains_only_message_entry_construction_fields() -> None:
    """Verify the public builder does not absorb tree, task, access, or I/O data."""
    constructor_parameters = tuple(inspect.signature(MessageEntryBuilder).parameters)
    public_methods = {
        name
        for name, _ in inspect.getmembers(MessageEntryBuilder, inspect.isfunction)
        if not name.startswith("_")
    }

    # Required identity matches MessageEntry while explicit fluent methods cover
    # only its remaining constructor fields and final immutable conversion.
    assert constructor_parameters == ("entry_id", "role")
    assert public_methods == {
        "add_content",
        "add_relation",
        "build",
        "with_extensions",
        "with_metadata",
    }
    for unrelated_name in (
        "sub_elements",
        "temperature",
        "authorization",
        "endpoint",
        "payload",
        "transport",
    ):
        assert unrelated_name not in constructor_parameters
        assert unrelated_name not in public_methods
