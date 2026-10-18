"""Semantic validation for complete immutable message documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_content import MessageContent
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_element import MessageElement
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_entry import MessageEntry
from mconet.core.domain.message_entry_validation import validate_message_entry
from mconet.core.domain.message_group import MessageGroup
from mconet.core.domain.message_group_validation import validate_message_group
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.tool_call_element import ToolCallElement
from mconet.core.domain.tool_call_element_validation import validate_tool_call_element
from mconet.core.domain.tool_result_element import ToolResultElement
from mconet.core.domain.tool_result_element_validation import (
    validate_tool_result_element,
)

_DOCUMENT_PURPOSES = frozenset(("input", "output", "context", "custom"))


def validate_message_document(document: MessageDocument) -> MessageDocument:
    """Validate one complete message tree and all document-local references.

    Args:
        document: The concrete immutable message document to validate.

    Returns:
        The same document object after successful validation.

    Raises:
        TypeError: If the document or one of its fields has an invalid runtime
            type.
        ValueError: If version, purpose, root, tree, IDs, relations, or JSON data
            violates message document semantics.

    Notes:
        Traversal is iterative so deeply nested valid documents do not depend on
        Python's recursion limit. Elements and content share one document-local
        ID namespace. Relations resolve only against element IDs and are checked
        after the complete tree index exists, which permits forward references.
    """
    candidate = cast(object, document)
    # Require the nominal root value because this validator composes concrete
    # Entry and Group validators and owns whole-document invariants.
    if not isinstance(candidate, MessageDocument):
        raise TypeError("document must be a MessageDocument.")

    version = cast(object, candidate.version)
    purpose = cast(object, candidate.purpose)
    root = cast(object, candidate.root)
    # Version remains forward-compatible opaque text; only values that cannot
    # identify any document format are rejected at this shared boundary.
    if not isinstance(version, str):
        raise TypeError("MessageDocument version must be a string.")
    if not version or version.isspace():
        raise ValueError("MessageDocument version must not be empty or whitespace.")

    if not isinstance(purpose, str):
        raise TypeError("MessageDocument purpose must be a string.")
    if purpose not in _DOCUMENT_PURPOSES:
        raise ValueError(
            "MessageDocument purpose must be input, output, context, or custom."
        )
    if not isinstance(root, MessageGroup):
        raise TypeError("MessageDocument root must be a MessageGroup.")

    element_ids, relations = _validate_tree(root)
    # Relation resolution is a second pass so an edge may legally reference an
    # element declared later in preorder without depending on traversal order.
    for relation in relations:
        _validate_relation(relation, element_ids)
    # Placement uses the same leaf order an adapter reads. A call that does
    # not follow an assistant entry cannot be folded into a message.
    _validate_tool_call_placement(root)

    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_tree(root: MessageGroup) -> tuple[set[str], tuple[MessageRelation, ...]]:
    """Validate the complete tree and return its element index and relations."""
    element_ids: set[str] = set()
    all_ids: set[str] = set()
    relations: list[MessageRelation] = []
    active_objects: set[int] = set()
    pending: list[tuple[object, bool]] = [(root, False)]

    # Enter/leave frames provide cycle detection without recursive calls. Reversed
    # child pushes preserve producer preorder in the effective validation order.
    while pending:
        candidate, leaving = pending.pop()
        identity = id(candidate)
        if leaving:
            active_objects.remove(identity)
            continue
        if identity in active_objects:
            raise ValueError("MessageDocument element tree must not contain cycles.")
        if not isinstance(candidate, MessageElement):
            raise TypeError("MessageDocument tree must contain MessageElement values.")
        element = candidate

        active_objects.add(identity)
        pending.append((element, True))
        children, element_relations = _validate_element(element)

        element_id = _register_id(cast(object, element.id), "element id", all_ids)
        element_ids.add(element_id)
        relations.extend(element_relations)

        # Content participates in the document-local identity namespace but not
        # in tree traversal or relation endpoint resolution.
        if isinstance(element, MessageEntry):
            _register_content_ids(element.content, all_ids)

        if element is root:
            root_kind = element.kind
            if root_kind.id.value != "message.root":
                raise ValueError("MessageDocument root kind must be message.root.")

        pending.extend((child, False) for child in reversed(children))

    return element_ids, tuple(relations)


def _validate_element(
    element: MessageElement,
) -> tuple[tuple[MessageElement, ...], tuple[MessageRelation, ...]]:
    """Validate one concrete or open element and snapshot traversal fields."""
    # Concrete values delegate to their dedicated validators so leaf/container
    # rules have one owner. Open custom elements use the shared structural path.
    if isinstance(element, MessageEntry):
        validate_message_entry(element)
        return element.sub_elements, element.relations
    if isinstance(element, MessageGroup):
        validate_message_group(element)
        return element.sub_elements, element.relations
    if isinstance(element, ToolCallElement):
        validate_tool_call_element(element)
        return element.sub_elements, element.relations
    if isinstance(element, ToolResultElement):
        validate_tool_result_element(element)
        return element.sub_elements, element.relations
    return _validate_open_element(element)


def _validate_tool_call_placement(root: MessageGroup) -> None:
    """Require every tool call to follow an assistant entry in leaf order."""
    pending: list[MessageElement] = [root]
    leaves: list[MessageElement] = []
    # Children are pushed in reverse so the leaves are read left to right.
    # Containers only order those leaves; they are not themselves messages.
    while pending:
        element = pending.pop()
        if element.kind.composition == "container":
            pending.extend(reversed(tuple(element.sub_elements)))
            continue
        leaves.append(element)

    assistant_run = False
    for element in leaves:
        if isinstance(element, MessageEntry):
            role_id = cast(object, element.role.id)
            # Only the standard assistant role opens a run. Another role, even
            # one with assistant text in its raw spelling, does not.
            assistant_run = (
                isinstance(role_id, OpenIdentifier)
                and role_id.value == "message.assistant"
            )
            continue
        if isinstance(element, ToolCallElement):
            # Consecutive calls stay in the same run. A call with no assistant
            # entry before it has no message to carry it.
            if not assistant_run:
                raise ValueError("A tool call must follow an assistant message entry.")
            continue
        # A tool result or any other leaf ends the run. The next call needs
        # its own assistant entry.
        assistant_run = False


def _validate_open_element(
    element: MessageElement,
) -> tuple[tuple[MessageElement, ...], tuple[MessageRelation, ...]]:
    """Validate shared fields of a provider-defined MessageElement."""
    kind = cast(object, element.kind)
    name = cast(object, element.name)
    value = cast(object, element.value)
    if not isinstance(kind, MessageElementKind):
        raise TypeError("MessageElement kind must implement MessageElementKind.")

    identifier = cast(object, kind.id)
    category = cast(object, kind.category)
    composition = cast(object, kind.composition)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("MessageElement kind id must be an OpenIdentifier.")
    validate_open_identifier(identifier)
    if not isinstance(category, str):
        raise TypeError("MessageElement kind category must be a string.")
    if not isinstance(composition, str):
        raise TypeError("MessageElement kind composition must be a string.")
    if composition not in ("leaf", "container"):
        raise ValueError("MessageElement kind composition must be leaf or container.")

    if name is not None and not isinstance(name, str):
        raise TypeError("MessageElement name must be a string or None.")
    _validate_json_mapping(cast(object, element.attributes), "element attributes")
    if value is not None:
        validate_json_value_numbers(cast(JsonValue, value))
    _validate_json_mapping(cast(object, element.metadata), "element metadata")
    _validate_json_mapping(cast(object, element.extensions), "element extensions")

    children = _snapshot_elements(cast(object, element.sub_elements))
    # Composition controls actual traversal shape even for open custom elements;
    # a leaf cannot hide child nodes behind a provider-defined Kind.
    if composition == "leaf" and children:
        raise ValueError("MessageElement leaf sub_elements must be empty.")
    relations = _snapshot_relations(cast(object, element.relations))
    return children, relations


def _snapshot_elements(value: object) -> tuple[MessageElement, ...]:
    """Snapshot an ordered sequence containing only MessageElement values."""
    # Structural implementations may expose any Sequence, unlike the concrete
    # immutable SDK values. Snapshot once so later caller mutation cannot alter
    # the traversal currently being validated.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("MessageElement sub_elements must be a sequence.")
    snapshot = tuple(cast(Sequence[object], value))
    if any(not isinstance(child, MessageElement) for child in snapshot):
        raise TypeError(
            "MessageElement sub_elements must contain MessageElement values."
        )
    return cast(tuple[MessageElement, ...], snapshot)


def _snapshot_relations(value: object) -> tuple[MessageRelation, ...]:
    """Snapshot an ordered sequence containing only MessageRelation values."""
    # Open elements may choose a mutable sequence implementation, so traversal
    # owns one stable relation snapshot before the document-wide second pass.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("MessageElement relations must be a sequence.")
    snapshot = tuple(cast(Sequence[object], value))
    if any(not isinstance(relation, MessageRelation) for relation in snapshot):
        raise TypeError("MessageElement relations must contain MessageRelation values.")
    return cast(tuple[MessageRelation, ...], snapshot)


def _register_content_ids(
    content: tuple[MessageContent, ...], all_ids: set[str]
) -> None:
    """Register every entry content ID without traversing content as elements."""
    for item in content:
        # MessageElement and MessageContent protocols overlap structurally in
        # Python. Explicitly reject element objects to preserve the domain split.
        if isinstance(item, MessageElement):
            raise ValueError(
                "MessageDocument content must not contain MessageElement values."
            )
        _register_id(cast(object, item.id), "content id", all_ids)


def _register_id(value: object, field_name: str, all_ids: set[str]) -> str:
    """Validate and register one ID in the shared document-local namespace."""
    # Element and content IDs use exact opaque text. A single set prevents an ID
    # from ambiguously naming different objects or crossing the two domains.
    if not isinstance(value, str):
        raise TypeError(f"MessageDocument {field_name} must be a string.")
    if not value or value.isspace():
        raise ValueError(
            f"MessageDocument {field_name} must not be empty or whitespace."
        )
    if value in all_ids:
        raise ValueError("MessageDocument element and content ids must be unique.")
    all_ids.add(value)
    return value


def _validate_relation(relation: MessageRelation, element_ids: set[str]) -> None:
    """Validate one relation and resolve both endpoints against element IDs."""
    source = cast(object, relation.source)
    target = cast(object, relation.target)
    relation_type = cast(object, relation.type)
    if not isinstance(source, str):
        raise TypeError("MessageRelation source must be a string.")
    if not source or source.isspace():
        raise ValueError("MessageRelation source must not be empty or whitespace.")
    if not isinstance(target, str):
        raise TypeError("MessageRelation target must be a string.")
    if not target or target.isspace():
        raise ValueError("MessageRelation target must not be empty or whitespace.")

    if not isinstance(relation_type, OpenIdentifier):
        raise TypeError("MessageRelation type must be an OpenIdentifier.")
    validate_open_identifier(relation_type)
    _validate_json_mapping(cast(object, relation.metadata), "relation metadata")

    # Relations connect elements, never MessageContent IDs. Source and target
    # are independent, and neither is inferred from the element storing the edge.
    if source not in element_ids:
        raise ValueError("MessageRelation source must reference an element id.")
    if target not in element_ids:
        raise ValueError("MessageRelation target must reference an element id.")


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JSON values."""
    # All document, element, and relation object channels use the same portable
    # Mapping boundary while retaining unknown keys without interpretation.
    if not isinstance(value, Mapping):
        raise TypeError(f"MessageDocument {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"MessageDocument {field_name} keys must be strings.")
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
