"""Open structural contract tests for custom MessageContent implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    MessageContent,
    MessageContentKind,
    MessageElement,
    OpenIdentifier,
)


def _empty_extensions() -> Extensions:
    """Return an independent empty JSON mapping for each content field."""
    # Separate dictionaries avoid shared mutable defaults while keeping the test
    # implementation focused on protocol shape rather than storage policy.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Custom content kind implemented without an SDK base class."""

    id: OpenIdentifier
    """Open content-representation identifier."""


@dataclass(frozen=True, slots=True)
class _Content:
    """Custom content item proving inheritance-free protocol conformance."""

    id: str
    """Document-local content identifier."""

    kind: MessageContentKind
    """Open content representation kind."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Descriptive JSON metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown versioned content fields."""


def _require_message_content(content: MessageContent) -> MessageContent:
    """Return a statically accepted content item without adapting it."""
    # Passing the object through unchanged proves structural conformance needs no
    # inheritance, registry lookup, or message-element conversion layer.
    return content


def test_custom_message_content_satisfies_complete_protocol() -> None:
    """Verify a provider-defined content item exposes all shared fields."""
    kind: MessageContentKind = _Kind(OpenIdentifier("vendor.rich_text"))
    content = _Content(
        id="content-1",
        kind=kind,
        metadata={"language": "zh-CN"},
        extensions={"vendorFormatting": {"version": 2}},
    )

    # Static and runtime recognition preserve the unknown kind and both JSON
    # channels without requiring a concrete payload class in the shared protocol.
    accepted = _require_message_content(content)
    assert isinstance(content, MessageContent)
    assert accepted is content
    assert accepted.id == "content-1"
    assert accepted.kind is kind
    assert accepted.kind.id.value == "vendor.rich_text"
    assert accepted.metadata == {"language": "zh-CN"}
    assert accepted.extensions == {"vendorFormatting": {"version": 2}}


def test_message_content_is_not_a_message_element_tree_node() -> None:
    """Verify the content contract has no element-tree or generic-value surface."""
    content = _Content(
        "content-1",
        _Kind(OpenIdentifier("content.text")),
    )

    # Content has no element name, attributes, value, children, or relations, so
    # tree traversal cannot accidentally consume it as a MessageElement.
    assert not isinstance(content, MessageElement)
    assert not hasattr(content, "name")
    assert not hasattr(content, "attributes")
    assert not hasattr(content, "value")
    assert not hasattr(content, "sub_elements")
    assert not hasattr(content, "relations")


def test_message_content_protocol_does_not_define_payload_fields() -> None:
    """Verify concrete payload storage remains owned by content implementations."""

    @dataclass(frozen=True, slots=True)
    class _ProviderContent(_Content):
        """Add a provider payload outside the shared content protocol."""

        payload: str = ""
        """Provider-defined representation payload."""

    content = _ProviderContent(
        id="content-1",
        kind=_Kind(OpenIdentifier("vendor.rich_text")),
        payload="Hello",
    )

    # Extra structural fields are allowed, but consumers of MessageContent see
    # only shared identity and data until they select the concrete content kind.
    accepted = _require_message_content(content)
    assert isinstance(content, MessageContent)
    assert accepted.id == "content-1"
    assert content.payload == "Hello"
    assert not hasattr(MessageContent, "payload")


def test_message_content_requires_the_complete_shared_surface() -> None:
    """Verify content-like objects missing shared data fields do not conform."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteContent:
        """Intentionally expose only content identity and kind."""

        id: str
        """Candidate document-local content identifier."""

        kind: MessageContentKind
        """Candidate content kind without metadata or extensions."""

    candidate = _IncompleteContent(
        "incomplete",
        _Kind(OpenIdentifier("vendor.incomplete")),
    )

    # Both JSON data channels are part of every content item; identity and kind
    # alone cannot satisfy the complete structural contract.
    assert not isinstance(candidate, MessageContent)
    assert not isinstance(cast(object, candidate.kind), MessageContent)
