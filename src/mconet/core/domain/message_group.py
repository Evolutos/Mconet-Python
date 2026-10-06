"""Immutable ordered container for message document tree elements."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_element import MessageElement
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_element_value import MessageElementValue
from mconet.core.domain.message_relation import MessageRelation

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by group defaults."""
    # The mapping contains no nested state and rejects writes, so sharing it
    # avoids allocations without creating caller-visible mutable global data.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class MessageGroup:
    """Group ordered message elements under an open container Kind.

    A group implements the complete :class:`MessageElement` data surface while
    keeping child elements in an immutable tuple. Its open Kind can represent
    standard root, history, current, turn, or bundle groups as well as future
    provider-defined containers. The class has no ``content`` field: message
    payloads remain owned by leaf entries and their MessageContent collections.

    Construction enforces immutable storage shape only. Container composition,
    child ID rules, recursive JSON validation, relation resolution, and graph
    consistency belong to the dedicated group and document validators.
    """

    id: str
    """Stable group identifier local to the enclosing message document."""

    kind: MessageElementKind
    """Open element Kind whose composition is validated separately."""

    sub_elements: tuple[MessageElement, ...]
    """Child message elements in exact producer-supplied order."""

    name: str | None = None
    """Optional producer-supplied group name."""

    attributes: Extensions = field(default_factory=_empty_extensions)
    """Read-only Kind-specific JSON attribute snapshot."""

    value: MessageElementValue | None = None
    """Optional generic JSON element value, never a MessageContent object."""

    relations: tuple[MessageRelation, ...] = ()
    """Directed element relations in exact declaration order."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control metadata snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require immutable field shapes and detach mapping membership."""
        group_id = cast(object, self.id)
        kind = cast(object, self.kind)
        sub_elements = cast(object, self.sub_elements)
        name = cast(object, self.name)
        relations = cast(object, self.relations)

        # Preserve exact identifier and name text. Non-empty rules and Kind
        # semantics need the dedicated validator and are not normalized here.
        if not isinstance(group_id, str):
            raise TypeError("MessageGroup id must be a string.")
        if not isinstance(kind, MessageElementKind):
            raise TypeError("MessageGroup kind must implement MessageElementKind.")
        if name is not None and not isinstance(name, str):
            raise TypeError("MessageGroup name must be a string or None.")

        # Tuple storage prevents post-construction reordering. Structural element
        # recognition admits custom message elements without a registry or base class.
        if not isinstance(sub_elements, tuple):
            raise TypeError("MessageGroup sub_elements must be a tuple.")
        for element in cast(tuple[object, ...], sub_elements):
            if not isinstance(element, MessageElement):
                raise TypeError(
                    "MessageGroup sub_elements must contain MessageElement values."
                )

        # Relations are immutable values and retain declaration order. Endpoint
        # existence cannot be decided without the enclosing document element index.
        if not isinstance(relations, tuple):
            raise TypeError("MessageGroup relations must be a tuple.")
        for relation in cast(tuple[object, ...], relations):
            if not isinstance(relation, MessageRelation):
                raise TypeError(
                    "MessageGroup relations must contain MessageRelation values."
                )

        # Snapshot each Mapping independently so caller membership changes cannot
        # alter the frozen group after it becomes part of a message tree.
        object.__setattr__(
            self,
            "attributes",
            _snapshot_mapping(self.attributes, "attributes"),
        )
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Accept the public Mapping abstraction while rejecting containers that do
    # not represent named JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"MessageGroup {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"MessageGroup {field_name} keys must be strings.")

    # Preserve values exactly and defer recursive JSON/number rules to the group
    # validator while isolating top-level membership from caller mutation.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
