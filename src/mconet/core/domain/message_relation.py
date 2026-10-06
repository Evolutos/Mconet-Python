"""Immutable references between elements in one message document."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.open_identifier import OpenIdentifier

_EMPTY_METADATA: Extensions = MappingProxyType({})


def _empty_metadata() -> Extensions:
    """Return the shared immutable empty metadata mapping."""
    # The mapping contains no nested values and rejects mutation, so sharing it
    # avoids per-relation allocation without exposing shared writable state.
    return _EMPTY_METADATA


@dataclass(frozen=True, slots=True)
class MessageRelation:
    """Describe a typed directed reference between message elements.

    ``source`` and ``target`` are document-local element identifiers. This value
    object preserves their direction and relation type without resolving either
    endpoint; the enclosing message-document validator owns existence and graph
    consistency checks. Metadata is descriptive JSON data and cannot replace an
    endpoint or change traversal semantics.
    """

    source: str
    """Document-local identifier of the element where the relation originates."""

    target: str
    """Document-local identifier of the element referenced by the relation."""

    type: OpenIdentifier
    """Open identifier describing the directed relation semantics."""

    metadata: Extensions = field(default_factory=_empty_metadata)
    """Read-only JSON metadata associated with this relation."""

    def __post_init__(self) -> None:
        """Require exact field shapes and freeze validated metadata membership."""
        source = cast(object, self.source)
        target = cast(object, self.target)
        relation_type = cast(object, self.type)

        # Preserve endpoint text exactly and validate only its primitive storage
        # type. Resolution, non-empty ID rules, and endpoint existence belong to
        # the enclosing document validator, which has access to every element.
        if not isinstance(source, str):
            raise TypeError("MessageRelation source must be a string.")
        if not isinstance(target, str):
            raise TypeError("MessageRelation target must be a string.")
        # Require the nominal open-identifier value while leaving namespace and
        # known-type policy open for custom relations and later validation.
        if not isinstance(relation_type, OpenIdentifier):
            raise TypeError("MessageRelation type must be an OpenIdentifier.")

        # Detach top-level membership from caller-owned mappings before the
        # immutable relation becomes visible to document traversal and mapping.
        object.__setattr__(self, "metadata", _snapshot_metadata(self.metadata))


def _snapshot_metadata(value: Extensions) -> Extensions:
    """Validate relation metadata and return a read-only membership snapshot."""
    candidate = cast(object, value)
    # Accept the public Mapping abstraction, but reject non-mapping containers
    # and non-string keys that cannot be represented by a JSON object.
    if not isinstance(candidate, Mapping):
        raise TypeError("MessageRelation metadata must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("MessageRelation metadata keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Validate each recursive value before snapshotting so malformed containers,
    # cycles, unsafe integers, and non-finite numbers cannot enter the relation.
    for item in typed_source.values():
        validate_json_value_numbers(item)
    return MappingProxyType(dict(typed_source))
