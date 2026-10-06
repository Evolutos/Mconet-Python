"""Tests for fluent construction of immutable message documents."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageDocument,
    MessageDocumentBuilder,
    MessageElement,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    OpenIdentifier,
    TextMessageContent,
)

_DocumentPurpose = Literal["input", "output", "context", "custom"]


def _empty_extensions() -> Extensions:
    """Create independent extension storage for structural test fixtures."""
    # A fresh mapping prevents one role or Kind fixture from sharing mutable
    # unknown fields with another builder scenario.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide an open structural Kind for root and nested groups."""

    id: OpenIdentifier
    """Standard or provider-defined element Kind identity."""

    category: str
    """Producer-defined element classification category."""

    composition: Literal["leaf", "container"]
    """Tree composition used by group and document validation."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural role for entry fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined role identity."""

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
    """Require one action to raise the expected type and diagnostic fragment."""
    # Keep the exception boundary narrow so an unrelated failure cannot satisfy
    # a negative builder scenario or hide unexpected successful construction.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _entry(entry_id: str, content_id: str, text: str) -> MessageEntry:
    """Create one valid leaf entry for document builder trees."""
    # Explicit IDs and text keep tree-order and document-wide identity assertions
    # independent from fixture-generated values.
    return MessageEntry(
        entry_id,
        _Role(OpenIdentifier("message.user")),
        (TextMessageContent(content_id, text),),
    )


def _group(
    group_id: str,
    kind_id: str,
    children: tuple[MessageElement, ...] = (),
) -> MessageGroup:
    """Create one valid concrete container with caller-selected children."""
    # Standard and provider-defined group identifiers share the same open Kind
    # structure; only the document root receives an exact identifier rule.
    kind: MessageElementKind = _Kind(OpenIdentifier(kind_id), "group", "container")
    return MessageGroup(group_id, kind, children)


def _root(children: tuple[MessageElement, ...] = ()) -> MessageGroup:
    """Create the standard concrete root group required by a document."""
    # Keeping root construction outside the Builder proves it never invents or
    # mutates tree nodes while assembling the enclosing document value.
    return _group("root", "message.root", children)


def test_builder_matches_direct_document_construction() -> None:
    """Verify every builder field equals the direct immutable constructor result."""
    first = _entry("entry-1", "content-1", "Hello")
    second = _entry("entry-2", "content-2", "世界 👋")
    history = _group("history", "message.history", (first,))
    current = _group("current", "message.current", (second,))
    root = _root((history, current))
    metadata: Extensions = {"conversation": "example", "turns": 2}
    extensions: Extensions = {"vendor.trace": {"enabled": True}}

    builder = MessageDocumentBuilder("1.0", "input", root)
    returned = builder.with_metadata(metadata).with_extensions(extensions)
    built = builder.build()
    direct = MessageDocument(
        "1.0",
        "input",
        root,
        metadata=metadata,
        extensions=extensions,
    )

    # Builder identity supports fluent calls. Dataclass equality and root identity
    # prove it neither rebuilds nor reorders any part of the supplied tree.
    assert returned is builder
    assert built == direct
    assert built is not direct
    assert built.root is root
    assert built.root.sub_elements == (history, current)
    assert history.sub_elements == (first,)
    assert current.sub_elements == (second,)


def test_builder_supports_every_document_purpose_and_opaque_version() -> None:
    """Verify all declared purposes and future non-empty versions remain exact."""
    purposes: tuple[_DocumentPurpose, ...] = (
        "input",
        "output",
        "context",
        "custom",
    )

    # The Builder does not parse version text or infer purpose from the root;
    # each valid input reaches the immutable document unchanged.
    for purpose in purposes:
        root = _root()
        built = MessageDocumentBuilder("future-version", purpose, root).build()
        assert built.version == "future-version"
        assert built.purpose == purpose
        assert built.root is root


def test_builder_owns_channels_and_each_build_returns_a_fresh_snapshot() -> None:
    """Verify caller and later builder mutations cannot alter built documents."""
    metadata: dict[str, JsonValue] = {"turn": 1}
    extensions: dict[str, JsonValue] = {"vendor.mode": "initial"}
    root = _root()
    builder = (
        MessageDocumentBuilder("1.0", "context", root)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )

    # Membership is captured at the fluent boundary, so external changes made
    # before build cannot leak into the Builder's owned state.
    metadata["turn"] = 2
    extensions["vendor.extra"] = True
    first = builder.build()

    # Replacing Builder channels changes only later results. MessageDocument
    # snapshots ensure the first result retains its original independent values.
    builder.with_metadata({"turn": 3}).with_extensions({"vendor.mode": "later"})
    second = builder.build()
    assert first is not second
    assert first.root is root
    assert second.root is root
    assert first.metadata == {"turn": 1}
    assert first.extensions == {"vendor.mode": "initial"}
    assert second.metadata == {"turn": 3}
    assert second.extensions == {"vendor.mode": "later"}


def test_builders_do_not_share_default_mapping_state() -> None:
    """Verify separate document builders own independent default JSON channels."""
    first_builder = MessageDocumentBuilder("1.0", "input", _root())
    second_builder = MessageDocumentBuilder("1.0", "output", _root())
    first_builder.with_metadata({"owner": "first"}).with_extensions(
        {"vendor.owner": "first"}
    )

    # Mutating both channels of one Builder leaves a separately constructed
    # Builder at its own empty defaults.
    first = first_builder.build()
    second = second_builder.build()
    assert first.metadata == {"owner": "first"}
    assert first.extensions == {"vendor.owner": "first"}
    assert second.metadata == {}
    assert second.extensions == {}


def test_builder_delegates_complete_document_semantics() -> None:
    """Verify build applies version, purpose, root, ID, and JSON validation."""
    wrong_root_kind = _group("root", "message.history")
    duplicate_id_root = _root(
        (
            _group("left", "vendor.group", (_entry("same", "content-1", "a"),)),
            _group("right", "vendor.group", (_entry("same", "content-2", "b"),)),
        )
    )
    cases: tuple[tuple[MessageDocumentBuilder, type[BaseException], str], ...] = (
        (
            MessageDocumentBuilder("", "input", _root()),
            ValueError,
            "version must not be empty",
        ),
        (
            MessageDocumentBuilder(
                "1.0", cast(_DocumentPurpose, "vendor-purpose"), _root()
            ),
            ValueError,
            "purpose must be input, output, context, or custom",
        ),
        (
            MessageDocumentBuilder("1.0", "input", wrong_root_kind),
            ValueError,
            "root kind must be message.root",
        ),
        (
            MessageDocumentBuilder("1.0", "input", duplicate_id_root),
            ValueError,
            "element and content ids must be unique",
        ),
        (
            MessageDocumentBuilder("1.0", "input", _root()).with_metadata(
                {"invalid": cast(JsonValue, ("tuple",))}
            ),
            TypeError,
            "JsonValue",
        ),
    )

    # All semantic failures originate from validate_message_document during
    # build, demonstrating that the Builder owns no divergent rule copy.
    for builder, exception_type, message in cases:
        _assert_raises(exception_type, builder.build, message)


def test_builder_rejects_invalid_storage_shapes_without_partial_changes() -> None:
    """Verify constructor and fluent boundaries fail before mutating state."""
    root = _root()
    builder = MessageDocumentBuilder("1.0", "input", root)
    invalid_actions: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: MessageDocumentBuilder(cast(str, 1), "input", root),
            "version must be a string",
        ),
        (
            lambda: MessageDocumentBuilder("1.0", cast(_DocumentPurpose, 1), root),
            "purpose must be a string",
        ),
        (
            lambda: MessageDocumentBuilder(
                "1.0", "input", cast(MessageGroup, object())
            ),
            "root must be a MessageGroup",
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

    # Each failed fluent call validates before replacement. The original Builder
    # remains valid and produces its untouched empty mapping channels.
    for action, message in invalid_actions:
        _assert_raises(TypeError, action, message)
    built = builder.build()
    assert built.root is root
    assert built.metadata == {}
    assert built.extensions == {}


def test_builder_surface_contains_only_document_construction_fields() -> None:
    """Verify the Builder excludes tree editing, task, access, and protocol data."""
    constructor_parameters = tuple(inspect.signature(MessageDocumentBuilder).parameters)
    public_methods = {
        name
        for name, _ in inspect.getmembers(MessageDocumentBuilder, inspect.isfunction)
        if not name.startswith("_")
    }

    # Required constructor inputs match MessageDocument and the only fluent
    # channels are its two optional mappings plus immutable conversion.
    assert constructor_parameters == ("version", "purpose", "root")
    assert public_methods == {"build", "with_extensions", "with_metadata"}
    for unrelated_name in (
        "add_entry",
        "sub_elements",
        "temperature",
        "authorization",
        "endpoint",
        "payload",
        "protocol",
        "transport",
    ):
        assert unrelated_name not in constructor_parameters
        assert unrelated_name not in public_methods
