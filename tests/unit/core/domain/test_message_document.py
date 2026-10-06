"""Field and ownership tests for immutable MessageDocument values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from typing import Literal, cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageDocument,
    MessageElementKind,
    MessageGroup,
    OpenIdentifier,
)

_DocumentPurpose = Literal["input", "output", "context", "custom"]


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a complete structural root Kind for document fixtures."""

    id: OpenIdentifier
    """Standard root Kind identifier."""

    category: str
    """Producer-defined root category."""

    composition: Literal["leaf", "container"]
    """Root composition retained for later validation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow exception boundary prevents an unrelated failure from satisfying
    # a storage-shape assertion accidentally.
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


def _root(*children: MessageGroup) -> MessageGroup:
    """Create a root group with optional nested group children in exact order."""
    # The helper builds only ordinary production values; passing children through
    # unchanged makes document identity and ordering assertions straightforward.
    return MessageGroup(
        "root",
        _Kind(OpenIdentifier("message.root"), "group", "container"),
        children,
    )


def test_message_document_preserves_version_purpose_and_root_identity() -> None:
    """Verify the three required document fields remain separate and exact."""
    history = MessageGroup(
        "history",
        _Kind(OpenIdentifier("message.history"), "group", "container"),
        (),
    )
    current = MessageGroup(
        "current",
        _Kind(OpenIdentifier("message.current"), "group", "container"),
        (),
    )
    root = _root(history, current)
    document = MessageDocument("1.0", "input", root)

    # No field is derived from another: version and purpose retain exact text,
    # while the root and its ordered subtree are preserved by object identity.
    assert document.version == "1.0"
    assert document.purpose == "input"
    assert document.root is root
    assert document.root.sub_elements == (history, current)
    assert document.root.sub_elements[0] is history
    assert document.root.sub_elements[1] is current
    assert document.metadata == {}
    assert document.extensions == {}


def test_message_document_accepts_every_declared_purpose() -> None:
    """Verify all four architecture-defined purpose values remain distinguishable."""
    purposes: tuple[_DocumentPurpose, ...] = (
        "input",
        "output",
        "context",
        "custom",
    )
    documents = tuple(MessageDocument("1.0", purpose, _root()) for purpose in purposes)

    # Direct equality proves the type does not collapse purpose into input/output
    # booleans, infer it from the root, or substitute one value for another.
    assert tuple(document.purpose for document in documents) == purposes


def test_message_document_snapshots_json_channels_and_is_immutable() -> None:
    """Verify mapping membership and dataclass fields cannot change after creation."""
    metadata: dict[str, JsonValue] = {"locale": "zh-CN"}
    extensions: dict[str, JsonValue] = {"vendorField": {"enabled": True}}
    document = MessageDocument(
        "1.0",
        "context",
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
        lambda: document.__setattr__("purpose", "output"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], document.metadata)),
        "does not support item assignment",
    )


def test_message_document_constructor_contains_only_message_fields() -> None:
    """Verify task, access, and protocol concerns cannot enter the document."""
    parameters = tuple(inspect.signature(MessageDocument).parameters)

    # The surface mirrors the language-neutral document contract exactly; no
    # generation setting, credential, endpoint, transport, or payload is present.
    assert parameters == (
        "version",
        "purpose",
        "root",
        "metadata",
        "extensions",
    )
    assert "temperature" not in parameters
    assert "authorization" not in parameters
    assert "endpoint" not in parameters
    assert "transport" not in parameters
    assert "payload" not in parameters


def test_message_document_definition_defers_semantic_validation() -> None:
    """Verify malformed semantic text and root Kind remain validator concerns."""
    leaf_root = MessageGroup(
        "",
        _Kind(OpenIdentifier("vendor.pending_root"), "group", "leaf"),
        (),
    )
    document = MessageDocument(
        "",
        cast(_DocumentPurpose, "vendor-purpose"),
        leaf_root,
    )

    # Construction preserves source data without normalization. The dedicated
    # Validator later checks version, purpose, root ID, Kind, and tree semantics.
    assert document.version == ""
    assert document.purpose == "vendor-purpose"
    assert document.root is leaf_root
    assert document.root.kind.composition == "leaf"


def test_message_document_requires_concrete_message_group_root() -> None:
    """Verify a structurally unrelated object cannot masquerade as the root."""
    kind: MessageElementKind = _Kind(
        OpenIdentifier("message.root"), "group", "container"
    )

    # Kind alone is insufficient: document traversal requires the concrete Group
    # value that owns children, relations, metadata, and extension fields.
    _assert_raises(
        TypeError,
        lambda: MessageDocument("1.0", "input", cast(MessageGroup, kind)),
        "root must be a MessageGroup",
    )


def test_message_document_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass primitive and Mapping field contracts."""
    root = _root()
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: MessageDocument(cast(str, 1), "input", root),
            "version must be a string",
        ),
        (
            lambda: MessageDocument("1.0", cast(_DocumentPurpose, 1), root),
            "purpose must be a string",
        ),
        (
            lambda: MessageDocument(
                "1.0", "input", root, metadata=cast(Extensions, [])
            ),
            "metadata must be a mapping",
        ),
        (
            lambda: MessageDocument(
                "1.0", "input", root, metadata=cast(Extensions, {1: True})
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: MessageDocument(
                "1.0", "input", root, extensions=cast(Extensions, "invalid")
            ),
            "extensions must be a mapping",
        ),
        (
            lambda: MessageDocument(
                "1.0", "input", root, extensions=cast(Extensions, {1: True})
            ),
            "extensions keys must be strings",
        ),
    )

    # Only storage shape is checked here; recursive JSON and semantic rules are
    # intentionally exercised by the following dedicated Validator work.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
