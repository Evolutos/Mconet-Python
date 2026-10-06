"""Open structural contract tests for custom MessageElement implementations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    MessageElement,
    MessageElementKind,
    MessageElementValue,
    MessageRelation,
    OpenIdentifier,
)


def _empty_extensions() -> Extensions:
    """Return a new empty JSON mapping for each custom element field."""
    # Independent dictionaries prevent one fixture's attributes, metadata, or
    # extensions membership from becoming shared state in another fixture.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Custom element kind used without inheriting an SDK implementation."""

    id: OpenIdentifier
    """Open element-kind identifier."""

    category: str
    """Producer-defined message category."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition supplied by the test fixture."""


@dataclass(frozen=True, slots=True)
class _Element:
    """Custom message element proving inheritance-free protocol conformance."""

    id: str
    """Document-local element identifier."""

    kind: MessageElementKind
    """Open kind describing this element."""

    name: str | None = None
    """Optional producer-supplied name."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Element-specific JSON attributes."""

    value: MessageElementValue | None = None
    """Optional direct JSON element value."""

    sub_elements: Sequence[MessageElement] = ()
    """Ordered child element sequence."""

    relations: Sequence[MessageRelation] = ()
    """Ordered directed relation sequence."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown versioned element fields."""


def _require_message_element(element: MessageElement) -> MessageElement:
    """Return a statically accepted message element without adapting it."""
    # Passing the object through this boundary proves structural typing is
    # sufficient and no SDK base class, task node, or registration is required.
    return element


def test_custom_message_element_satisfies_complete_protocol() -> None:
    """Verify a custom element exposes every message-domain field independently."""
    kind: MessageElementKind = _Kind(
        OpenIdentifier("vendor.annotation"), "annotation", "leaf"
    )
    relation = MessageRelation(
        source="annotation-1",
        target="entry-1",
        type=OpenIdentifier("vendor.annotates"),
        metadata={"weight": 0.8},
    )
    element = _Element(
        id="annotation-1",
        kind=kind,
        name="review-note",
        attributes={"visibility": "internal"},
        value={"text": "Check this answer."},
        relations=(relation,),
        metadata={"reviewer": "quality"},
        extensions={"vendorField": {"enabled": True}},
    )

    # Runtime and static structural recognition use only message fields; no
    # inheritance, registration hook, task descriptor, or TaskNode is present.
    accepted = _require_message_element(element)
    assert isinstance(element, MessageElement)
    assert accepted is element
    assert accepted.id == "annotation-1"
    assert accepted.kind is kind
    assert accepted.name == "review-note"
    assert accepted.attributes == {"visibility": "internal"}
    assert accepted.value == {"text": "Check this answer."}
    assert tuple(accepted.relations) == (relation,)
    assert accepted.metadata == {"reviewer": "quality"}
    assert accepted.extensions == {"vendorField": {"enabled": True}}


def test_message_element_preserves_ordered_recursive_children() -> None:
    """Verify child order and recursive protocol typing remain observable."""
    leaf_kind: MessageElementKind = _Kind(
        OpenIdentifier("message.entry"), "entry", "leaf"
    )
    container_kind: MessageElementKind = _Kind(
        OpenIdentifier("vendor.section"), "group", "container"
    )
    first: MessageElement = _Element("first", leaf_kind, value="one")
    second: MessageElement = _Element("second", leaf_kind, value="two")
    container = _Element(
        "section",
        container_kind,
        sub_elements=[first, second],
    )

    # Sequence exposes stable producer order without constraining custom storage
    # to one Python container type, and each child retains the same protocol.
    assert isinstance(container, MessageElement)
    assert [child.id for child in container.sub_elements] == ["first", "second"]
    assert all(isinstance(child, MessageElement) for child in container.sub_elements)


def test_message_element_protocol_does_not_enforce_tree_validation() -> None:
    """Verify structural conformance does not perform kind composition checks."""
    leaf_kind: MessageElementKind = _Kind(
        OpenIdentifier("vendor.leaf"), "custom", "leaf"
    )
    child: MessageElement = _Element("child", leaf_kind)
    structurally_complete = _Element(
        "parent",
        leaf_kind,
        sub_elements=(child,),
    )

    # A runtime protocol can only recognize the complete field surface. Later
    # validators own semantic rules such as prohibiting children on leaf kinds.
    assert isinstance(structurally_complete, MessageElement)
    assert tuple(structurally_complete.sub_elements) == (child,)


def test_message_element_requires_the_complete_field_surface() -> None:
    """Verify element-like objects missing message fields do not conform."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteElement:
        """Intentionally omit all fields except identity and kind."""

        id: str
        """Document-local candidate identifier."""

        kind: MessageElementKind
        """Candidate element kind without the remaining protocol fields."""

    candidate = _IncompleteElement(
        "incomplete",
        _Kind(OpenIdentifier("vendor.incomplete"), "custom", "leaf"),
    )

    # Identity and kind alone cannot substitute for value, children, relations,
    # metadata, extensions, and the other required message-domain channels.
    assert not isinstance(candidate, MessageElement)
    assert not isinstance(cast(object, candidate.kind), MessageElement)
