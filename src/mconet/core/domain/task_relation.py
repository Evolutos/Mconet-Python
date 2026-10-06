"""Immutable directed references between nodes in one task document."""

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
    """Return the shared immutable empty relation metadata mapping."""
    # Empty membership has no nested state and rejects mutation, so sharing the
    # default avoids allocation without coupling independent relation values.
    return _EMPTY_METADATA


@dataclass(frozen=True, slots=True)
class TaskRelation:
    """Describe a typed directed reference between task nodes.

    ``source`` and ``target`` are identifiers local to one enclosing TaskDocument.
    This value preserves direction, open relation semantics, and descriptive
    metadata without resolving either endpoint. Whole-document validation owns
    node existence, uniqueness, graph consistency, and relation-type syntax.
    """

    source: str
    """Document-local identifier of the node where the relation originates."""

    target: str
    """Document-local identifier of the node referenced by the relation."""

    type: OpenIdentifier
    """Open identifier describing the directed task relation semantics."""

    metadata: Extensions = field(default_factory=_empty_metadata)
    """Read-only portable JSON metadata associated with this relation."""

    def __post_init__(self) -> None:
        """Require exact field shapes and freeze validated metadata membership."""
        source = cast(object, self.source)
        target = cast(object, self.target)
        relation_type = cast(object, self.type)

        # Preserve endpoint text exactly and validate only primitive storage here.
        # Empty, duplicate, or missing IDs require the enclosing node index and
        # therefore remain visible to later TaskDocument validation.
        if not isinstance(source, str):
            raise TypeError("TaskRelation source must be a string.")
        if not isinstance(target, str):
            raise TypeError("TaskRelation target must be a string.")

        # The nominal identifier keeps relation semantics open. Portable syntax
        # and any known-type policy remain separate from value construction.
        if not isinstance(relation_type, OpenIdentifier):
            raise TypeError("TaskRelation type must be an OpenIdentifier.")

        # Detach top-level membership from caller-owned mappings before the frozen
        # relation becomes observable by task traversal and mapping components.
        object.__setattr__(self, "metadata", _snapshot_metadata(self.metadata))


def _snapshot_metadata(value: Extensions) -> Extensions:
    """Validate relation metadata and return read-only membership storage."""
    candidate = cast(object, value)
    # Accept custom Mapping implementations while rejecting arrays, scalars, and
    # non-string keys that cannot form a language-neutral JSON object.
    if not isinstance(candidate, Mapping):
        raise TypeError("TaskRelation metadata must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("TaskRelation metadata keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Validate recursive values before snapshotting so cycles, host objects,
    # unsafe integers, and non-finite numbers cannot enter portable task data.
    for item in typed_source.values():
        validate_json_value_numbers(item)
    return MappingProxyType(dict(typed_source))
