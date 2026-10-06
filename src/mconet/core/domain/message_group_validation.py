"""Semantic validation for immutable message group container elements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_element import MessageElement
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_group import MessageGroup
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier


def validate_message_group(group: MessageGroup) -> MessageGroup:
    """Validate one message group without recursively validating its children.

    Args:
        group: The concrete immutable message group to validate.

    Returns:
        The same group object after successful validation.

    Raises:
        TypeError: If the group or one of its fields has an invalid runtime type.
        ValueError: If identity, Kind, child IDs, or JSON data is invalid.

    Notes:
        This function validates only the current container and its direct child
        identifiers. Child element semantics, document-wide ID uniqueness,
        relation endpoint resolution, and graph consistency require the complete
        MessageDocument and are intentionally deferred.
    """
    candidate = cast(object, group)
    # Require the nominal concrete type because this validator owns MessageGroup
    # container semantics rather than every structural MessageElement.
    if not isinstance(candidate, MessageGroup):
        raise TypeError("group must be a MessageGroup.")

    group_id = _validate_element_id(cast(object, candidate.id), "id")
    _validate_group_kind(cast(object, candidate.kind))

    name = cast(object, candidate.name)
    # Optional group names remain opaque and may be empty; only their declared
    # primitive type is shared across languages at this boundary.
    if name is not None and not isinstance(name, str):
        raise TypeError("MessageGroup name must be a string or None.")

    _validate_children(cast(object, candidate.sub_elements), group_id)
    _validate_json_mapping(cast(object, candidate.attributes), "attributes")

    value = cast(object, candidate.value)
    # A generic element value is independent from MessageContent but still must
    # be recursively portable JSON before a mapper or schema observes it.
    if value is not None:
        validate_json_value_numbers(cast(JsonValue, value))

    _validate_relations(cast(object, candidate.relations))
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_element_id(value: object, field_name: str) -> str:
    """Return one usable opaque document-local element identifier."""
    # IDs remain case-sensitive and are never trimmed or parsed as open Kind
    # identifiers. Only absence and all-whitespace values are unusable as keys.
    if not isinstance(value, str):
        raise TypeError(f"MessageGroup {field_name} must be a string.")
    if not value or value.isspace():
        raise ValueError(f"MessageGroup {field_name} must not be empty or whitespace.")
    return value


def _validate_group_kind(value: object) -> None:
    """Require an open portable Kind with container composition."""
    # Structural recognition keeps standard and provider-defined group Kinds
    # open while requiring the complete element classification surface.
    if not isinstance(value, MessageElementKind):
        raise TypeError("MessageGroup kind must implement MessageElementKind.")

    identifier = cast(object, value.id)
    category = cast(object, value.category)
    composition = cast(object, value.composition)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("MessageGroup kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)

    # Category is producer-defined and intentionally not mapped through a known
    # value table, but it must retain the protocol's declared string shape.
    if not isinstance(category, str):
        raise TypeError("MessageGroup kind category must be a string.")
    if not isinstance(composition, str):
        raise TypeError("MessageGroup kind composition must be a string.")
    if composition != "container":
        raise ValueError("MessageGroup kind composition must be container.")


def _validate_children(value: object, group_id: str) -> None:
    """Validate immutable direct children and their local ID relationships."""
    # Tuple storage preserves observation order throughout validation and prevents
    # a caller from inserting or removing children during this pass.
    if not isinstance(value, tuple):
        raise TypeError("MessageGroup sub_elements must be a tuple.")

    child_ids: set[str] = set()
    for child in cast(tuple[object, ...], value):
        if not isinstance(child, MessageElement):
            raise TypeError(
                "MessageGroup sub_elements must contain MessageElement values."
            )
        child_id = _validate_element_id(cast(object, child.id), "child id")
        # A parent/child collision creates two nodes with the same document-local
        # identity before any deeper traversal, so reject it at this local edge.
        if child_id == group_id:
            raise ValueError("MessageGroup child id must differ from group id.")
        if child_id in child_ids:
            raise ValueError("MessageGroup direct child ids must be unique.")
        child_ids.add(child_id)


def _validate_relations(value: object) -> None:
    """Require immutable ordered MessageRelation storage on the group."""
    # Relation endpoints require a document-wide index. This boundary guarantees
    # only a stable tuple of already constructed relation value objects.
    if not isinstance(value, tuple):
        raise TypeError("MessageGroup relations must be a tuple.")
    for relation in cast(tuple[object, ...], value):
        if not isinstance(relation, MessageRelation):
            raise TypeError(
                "MessageGroup relations must contain MessageRelation values."
            )


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    # Public fields accept any Mapping implementation, while language-neutral
    # JSON object keys remain strings for every producer and consumer.
    if not isinstance(value, Mapping):
        raise TypeError(f"MessageGroup {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"MessageGroup {field_name} keys must be strings.")

    # Validate each value independently because a general Mapping is not itself
    # required to be one of the concrete dict branches in JsonValue.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
