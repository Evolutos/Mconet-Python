"""Execution-scope tests for text-only message documents."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast
from unittest.mock import patch

from mconet.core.domain import (
    Extensions,
    MessageContent,
    MessageContentKind,
    MessageDocument,
    MessageElement,
    MessageElementKind,
    MessageElementValue,
    MessageEntry,
    MessageGroup,
    MessageRelation,
    MessageRole,
    ModelInteractionError,
    OpenIdentifier,
    TextMessageContent,
    validate_text_message_content_scope,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for structural fixtures."""
    # Fresh dictionaries prevent one custom value from mutating another test's
    # metadata or extensions through shared default state.
    return {}


@dataclass(frozen=True, slots=True)
class _ElementKind:
    """Provide a complete open Kind for groups and custom elements."""

    id: OpenIdentifier
    """Portable element classification identity."""

    category: str
    """Producer-defined element category."""

    composition: Literal["leaf", "container"]
    """Tree shape used by document and scope traversal."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural role for entry fixtures."""

    id: OpenIdentifier
    """Open participant role identity."""

    semantic: str | None = None
    """Optional producer guidance about the role."""

    raw_value: str | None = None
    """Optional exact external role spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable role data."""


@dataclass(frozen=True, slots=True)
class _ContentKind:
    """Provide one open MessageContent Kind identity."""

    id: OpenIdentifier
    """Portable content representation identity."""


@dataclass(frozen=True, slots=True)
class _UnknownContent:
    """Represent a valid open content type outside the supported text scope."""

    id: str
    """Document-local content identity."""

    kind: MessageContentKind
    """Open content classification."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive content data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable content fields."""


@dataclass(frozen=True, slots=True)
class _OpenElement:
    """Represent an open container with caller-owned Sequence storage."""

    id: str
    """Document-local element identity."""

    kind: MessageElementKind
    """Open element classification and composition."""

    name: str | None = None
    """Optional producer-defined name."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Kind-specific portable attributes."""

    value: MessageElementValue | None = None
    """Optional generic JSON value."""

    sub_elements: Sequence[MessageElement] = ()
    """Ordered child storage that may use a mutable implementation."""

    relations: Sequence[MessageRelation] = ()
    """Ordered directed relation storage."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive element data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable element fields."""


def _entry(
    entry_id: str,
    *content: MessageContent,
) -> MessageEntry:
    """Create one user entry containing the supplied ordered content."""
    # A fresh role and tuple preserve explicit content identity and order without
    # involving builders or protocol mapping in this scope-focused test.
    return MessageEntry(
        entry_id,
        cast(MessageRole, _Role(OpenIdentifier("message.user"))),
        content,
    )


def _group(
    group_id: str,
    kind_id: str,
    children: tuple[MessageElement, ...] = (),
) -> MessageGroup:
    """Create one concrete container group with exact ordered children."""
    # The helper keeps root and nested group construction identical except for
    # their open Kind IDs, isolating content-scope behavior from tree setup.
    return MessageGroup(
        group_id,
        _ElementKind(OpenIdentifier(kind_id), "group", "container"),
        children,
    )


def _document(children: tuple[MessageElement, ...] = ()) -> MessageDocument:
    """Create one valid input document around ordered root children."""
    # Every scenario receives a concrete standard root so full domain validation
    # succeeds unless the test deliberately corrupts another invariant.
    return MessageDocument("1.0", "input", _group("root", "message.root", children))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its message fragment."""
    # A narrow exception boundary ensures setup or domain-validation failures do
    # not accidentally satisfy a specific scope-policy assertion.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_text_message_content_scope_accepts_empty_and_ordered_text_documents() -> None:
    """Verify empty trees and multiple text items pass without replacement."""
    empty = _document()
    first = TextMessageContent("content-1", "first")
    second = TextMessageContent("content-2", "second")
    entry = _entry("entry-1", first, second)
    document = _document((entry,))

    # Identity and tuple assertions prove the gate performs no rebuilding,
    # merging, normalization, or reordering before later protocol adaptation.
    assert validate_text_message_content_scope(empty) is empty
    assert validate_text_message_content_scope(document) is document
    assert entry.content == (first, second)
    assert entry.content[0] is first
    assert entry.content[1] is second


def test_text_message_content_scope_traverses_open_nested_containers() -> None:
    """Verify text entries below provider containers remain discoverable."""
    content = TextMessageContent("content-1", "nested")
    entry = _entry("entry-1", content)
    container = _OpenElement(
        "provider-container",
        _ElementKind(OpenIdentifier("vendor.section"), "group", "container"),
        sub_elements=[entry],
    )
    document = _document((container,))

    # Open mutable Sequence storage is accepted by domain validation and then
    # snapshotted again by the scope traversal without changing caller state.
    assert validate_text_message_content_scope(document) is document
    assert container.sub_elements == [entry]
    assert entry.content == (content,)


def test_text_message_content_scope_rejects_unknown_content_stably() -> None:
    """Verify one nested non-text item returns the normalized support failure."""
    private_id = "private-content\nsecond-line"
    unknown = _UnknownContent(
        private_id,
        _ContentKind(OpenIdentifier("vendor.rich_text")),
        metadata={"format": "portable"},
    )
    entry = _entry(
        "entry-1",
        TextMessageContent("content-1", "before"),
        unknown,
        TextMessageContent("content-3", "after"),
    )
    document = _document((_group("nested", "message.history", (entry,)),))

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_text_message_content_scope(document),
            "Only TextMessageContent is supported",
        ),
    )

    # Stable fields are language-neutral, while producer identity, Kind, and
    # metadata remain absent from exception text to prevent log injection.
    assert error.category.id == OpenIdentifier("unsupported_feature")
    assert error.phase.id == OpenIdentifier("validation")
    assert error.code == "unsupported_message_content"
    assert error.message == "Only TextMessageContent is supported."
    assert private_id not in str(error)
    assert "vendor.rich_text" not in str(error)
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_text_message_content_scope_requires_the_concrete_text_type() -> None:
    """Verify an open value cannot masquerade through the text Kind alone."""
    structural_text = _UnknownContent(
        "content-1",
        _ContentKind(OpenIdentifier("content.text")),
    )
    document = _document((_entry("entry-1", structural_text),))

    # Kind identity selects interpretation only after the concrete payload has a
    # known contract; an unknown object has no guaranteed text field or mapper.
    _assert_raises(
        ModelInteractionError,
        lambda: validate_text_message_content_scope(document),
        "Only TextMessageContent is supported",
    )


def test_text_message_content_scope_validates_the_document_before_policy() -> None:
    """Verify malformed domain data is not relabeled as unsupported content."""
    unknown = _UnknownContent(
        "content-1",
        _ContentKind(OpenIdentifier("vendor.rich_text")),
    )
    invalid_root = _group("root", "message.history", (_entry("entry-1", unknown),))
    document = MessageDocument("1.0", "input", invalid_root)

    # Root identity is a domain error independent of content support. Running the
    # complete validator first preserves that more fundamental diagnostic.
    _assert_raises(
        ValueError,
        lambda: validate_text_message_content_scope(document),
        "root kind must be message.root",
    )


def test_text_message_content_scope_handles_deep_trees_iteratively() -> None:
    """Verify valid depth beyond recursion limits does not overflow the stack."""
    element: MessageElement = _entry(
        "entry-deep",
        TextMessageContent("content-deep", "text"),
    )
    for index in range(1_200):
        # Each immutable group consumes one tree level while retaining a unique
        # document-local ID required by complete domain validation.
        element = _group(
            f"group-{index}",
            "message.bundle",
            (element,),
        )
    document = _document((element,))

    # Both the composed document validator and scope pass use explicit worklists.
    assert validate_text_message_content_scope(document) is document


def test_text_message_content_scope_rechecks_changed_child_storage() -> None:
    """Verify a post-validation non-sequence child value fails safely."""
    container = _OpenElement(
        "provider-container",
        _ElementKind(OpenIdentifier("vendor.section"), "group", "container"),
    )
    document = _document((container,))
    object.__setattr__(container, "sub_elements", "changed-after-validation")

    # Replace only the completed validation call so this test can model mutation
    # in the narrow interval before the scope traversal takes its own snapshot.
    with patch(
        "mconet.core.domain.message_content_scope.validate_message_document",
        return_value=document,
    ):
        _assert_raises(
            TypeError,
            lambda: validate_text_message_content_scope(document),
            "sub_elements must be a sequence",
        )


def test_text_message_content_scope_rechecks_changed_child_members() -> None:
    """Verify post-validation non-element sequence members fail safely."""
    container = _OpenElement(
        "provider-container",
        _ElementKind(OpenIdentifier("vendor.section"), "group", "container"),
    )
    document = _document((container,))
    object.__setattr__(container, "sub_elements", [object()])

    # A list remains a Sequence, so the second guard must narrow every member
    # instead of allowing an arbitrary object onto the traversal worklist.
    with patch(
        "mconet.core.domain.message_content_scope.validate_message_document",
        return_value=document,
    ):
        _assert_raises(
            TypeError,
            lambda: validate_text_message_content_scope(document),
            "must contain MessageElement values",
        )


def test_text_message_content_scope_requires_a_message_document() -> None:
    """Verify dynamic callers cannot bypass the nominal document boundary."""
    # Delegating the trust boundary to complete document validation yields the
    # same precise TypeError before tree traversal or error construction begins.
    _assert_raises(
        TypeError,
        lambda: validate_text_message_content_scope(cast(MessageDocument, object())),
        "document must be a MessageDocument",
    )
