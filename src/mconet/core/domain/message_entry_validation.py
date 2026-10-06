"""Semantic validation for immutable message entry leaf elements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_content import MessageContent
from mconet.core.domain.message_content_kind import MessageContentKind
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_entry import MessageEntry
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.message_role import MessageRole
from mconet.core.domain.message_role_validation import validate_message_role
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.text_message_content import TextMessageContent
from mconet.core.domain.text_message_content_validation import (
    validate_text_message_content,
)


def validate_message_entry(entry: MessageEntry) -> MessageEntry:
    """Validate one message entry without changing its role or content order.

    Args:
        entry: The concrete immutable message entry to validate.

    Returns:
        The same entry object after successful validation.

    Raises:
        TypeError: If the entry or one of its fields has an invalid runtime type.
        ValueError: If identity, leaf semantics, role, content, or JSON data is
            invalid.

    Notes:
        Unknown structural MessageContent implementations remain valid at this
        domain boundary. A later release-scope check decides whether a concrete
        runtime supports them. Document-wide ID uniqueness and relation endpoint
        resolution also require the enclosing MessageDocument and are not
        performed here.
    """
    candidate = cast(object, entry)
    # Require the nominal concrete type because this validator owns the fixed
    # leaf invariants of MessageEntry, not arbitrary MessageElement protocols.
    if not isinstance(candidate, MessageEntry):
        raise TypeError("entry must be a MessageEntry.")

    entry_id = cast(object, candidate.id)
    # Entry identity must be usable as a document-local key. Preserve exact text
    # while rejecting values that cannot identify an element at all.
    if not isinstance(entry_id, str):
        raise TypeError("MessageEntry id must be a string.")
    if not entry_id or entry_id.isspace():
        raise ValueError("MessageEntry id must not be empty or whitespace.")

    # Validate fixed tree semantics before role and payload data so a malformed
    # non-leaf entry always fails at the structural boundary deterministically.
    _validate_entry_kind(cast(object, candidate.kind))
    _validate_fixed_element_fields(candidate)

    role = cast(object, candidate.role)
    # Delegate open role syntax and extension rules to the single shared Role
    # validator; unknown but portable roles remain lossless and valid.
    if not isinstance(role, MessageRole):
        raise TypeError("MessageEntry role must implement MessageRole.")
    validate_message_role(role)

    _validate_content(cast(object, candidate.content))
    _validate_relations(cast(object, candidate.relations))
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_entry_kind(value: object) -> None:
    """Require the exact portable Kind assigned to a message entry leaf."""
    # Structural recognition catches dynamic subclasses returning incomplete
    # Kind objects before their individual properties are inspected.
    if not isinstance(value, MessageElementKind):
        raise TypeError("MessageEntry kind must implement MessageElementKind.")

    identifier = cast(object, value.id)
    category = cast(object, value.category)
    composition = cast(object, value.composition)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("MessageEntry kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)
    # A concrete entry cannot be reclassified as another element kind even when
    # the replacement identifier is otherwise portable.
    if identifier.value != "message.entry":
        raise ValueError("MessageEntry kind id must be message.entry.")

    if not isinstance(category, str):
        raise TypeError("MessageEntry kind category must be a string.")
    if category != "entry":
        raise ValueError("MessageEntry kind category must be entry.")

    if not isinstance(composition, str):
        raise TypeError("MessageEntry kind composition must be a string.")
    if composition != "leaf":
        raise ValueError("MessageEntry kind composition must be leaf.")


def _validate_fixed_element_fields(entry: MessageEntry) -> None:
    """Require generic MessageElement fields to retain entry leaf semantics."""
    name = cast(object, entry.name)
    attributes = cast(object, entry.attributes)
    value = cast(object, entry.value)
    sub_elements = cast(object, entry.sub_elements)

    # Role is the only participant label and content is the only payload channel;
    # generic name, attributes, and value therefore have fixed empty states.
    if name is not None:
        raise ValueError("MessageEntry name must be None.")
    attribute_mapping = _require_mapping(attributes, "attributes")
    if attribute_mapping:
        raise ValueError("MessageEntry attributes must be empty.")
    if value is not None:
        raise ValueError("MessageEntry value must be None.")

    # Tuple storage is part of the immutable concrete contract. Any child makes
    # the entry non-leaf even if a dynamic Kind still claims leaf composition.
    if not isinstance(sub_elements, tuple):
        raise TypeError("MessageEntry sub_elements must be a tuple.")
    if sub_elements:
        raise ValueError("MessageEntry sub_elements must be empty for a leaf.")


def _validate_content(value: object) -> None:
    """Validate a non-empty ordered tuple of open message content values."""
    # Concrete entries use tuples so validation observes a stable order and
    # cannot race with caller insertion, removal, or reordering.
    if not isinstance(value, tuple):
        raise TypeError("MessageEntry content must be a tuple.")
    if not value:
        raise ValueError("MessageEntry content must not be empty.")

    for item in cast(tuple[object, ...], value):
        if not isinstance(item, MessageContent):
            raise TypeError("MessageEntry content must contain MessageContent values.")
        # Known text content uses its full concrete validator. Other open content
        # kinds receive shared structural validation and remain available for a
        # later runtime-scope decision instead of being rejected prematurely.
        if isinstance(item, TextMessageContent):
            validate_text_message_content(item)
        else:
            _validate_open_content(item)


def _validate_open_content(content: MessageContent) -> None:
    """Validate fields shared by an unknown structural content implementation."""
    content_id = cast(object, content.id)
    kind = cast(object, content.kind)
    # Content IDs remain document-owned opaque strings. Non-empty and uniqueness
    # policies require the complete document rather than this entry in isolation.
    if not isinstance(content_id, str):
        raise TypeError("MessageContent id must be a string.")
    if not isinstance(kind, MessageContentKind):
        raise TypeError("MessageContent kind must implement MessageContentKind.")

    identifier = cast(object, kind.id)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("MessageContent kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)

    # Unknown keys and values are not interpreted, but their recursive shapes
    # and numbers must remain portable before later mappers observe them.
    _validate_json_mapping(cast(object, content.metadata), "content metadata")
    _validate_json_mapping(cast(object, content.extensions), "content extensions")


def _validate_relations(value: object) -> None:
    """Require immutable ordered MessageRelation storage on the entry."""
    # Endpoint existence and graph rules need a document-wide element index, but
    # this local boundary still guarantees stable tuple storage and value types.
    if not isinstance(value, tuple):
        raise TypeError("MessageEntry relations must be a tuple.")
    for relation in cast(tuple[object, ...], value):
        if not isinstance(relation, MessageRelation):
            raise TypeError(
                "MessageEntry relations must contain MessageRelation values."
            )


def _require_mapping(value: object, field_name: str) -> Mapping[object, object]:
    """Return a mapping after enforcing string JSON object keys."""
    # Public domain channels accept any Mapping implementation, but portable
    # object keys remain strings regardless of the concrete Python container.
    if not isinstance(value, Mapping):
        raise TypeError(f"MessageEntry {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"MessageEntry {field_name} keys must be strings.")
    return mapping


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    mapping = _require_mapping(value, field_name)
    # Validate values independently because a general Mapping need not itself be
    # one of the concrete dict containers accepted by the recursive validator.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
