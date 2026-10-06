"""Immutable references to artifacts in one enclosing catalog."""

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
    """Return the shared immutable empty reference metadata mapping."""
    # Empty data has no nested membership and rejects mutation, so sharing this
    # default cannot leak caller state between independent reference values.
    return _EMPTY_METADATA


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Describe one typed reference into an enclosing ArtifactCatalog.

    ``artifact_id`` is meaningful only within the request or result catalog that
    owns this reference. The value object does not resolve that ID, search other
    catalogs, or access artifact content. Optional relation identity and metadata
    describe usage without changing the reference scope.
    """

    artifact_id: str
    """Catalog-local identifier of the referenced artifact."""

    relation: OpenIdentifier | None = None
    """Optional open identifier describing how the artifact is related."""

    metadata: Extensions = field(default_factory=_empty_metadata)
    """Read-only JSON metadata associated with this reference occurrence."""

    def __post_init__(self) -> None:
        """Require exact field types and freeze validated metadata membership."""
        artifact_id = cast(object, self.artifact_id)
        relation = cast(object, self.relation)

        # Preserve the local ID exactly and validate only primitive storage here.
        # Catalog existence and uniqueness require the enclosing catalog index.
        if not isinstance(artifact_id, str):
            raise TypeError("ArtifactReference artifact_id must be a string.")
        # Relation semantics remain open, but dynamic callers must still provide
        # the nominal identifier value rather than an arbitrary string.
        if relation is not None and not isinstance(relation, OpenIdentifier):
            raise TypeError(
                "ArtifactReference relation must be an OpenIdentifier or None."
            )

        # Detach top-level membership before the frozen reference is exposed so
        # caller dictionary changes cannot alter its observable value.
        object.__setattr__(self, "metadata", _snapshot_metadata(self.metadata))


def _snapshot_metadata(value: Extensions) -> Extensions:
    """Validate reference metadata and return a read-only membership snapshot."""
    candidate = cast(object, value)
    # Accept the public Mapping abstraction while rejecting arrays, scalars, and
    # non-string keys that cannot form a language-neutral JSON object.
    if not isinstance(candidate, Mapping):
        raise TypeError("ArtifactReference metadata must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ArtifactReference metadata keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Validate every recursive value before snapshotting so cycles, host objects,
    # unsafe integers, and non-finite numbers cannot enter portable references.
    for item in typed_source.values():
        validate_json_value_numbers(item)
    return MappingProxyType(dict(typed_source))
