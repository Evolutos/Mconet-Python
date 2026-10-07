"""Immutable message document and artifact catalog mapping result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import ArtifactCatalog, MessageDocument


@dataclass(frozen=True, slots=True)
class MessageMappingResult:
    """Return a mapped message document with its exact artifact scope.

    A response mapper produces both values as one indivisible result so callers
    never receive a document while losing the catalog that owns its artifact
    references. The result preserves both completed values by identity and does
    not parse bytes, map task results, merge catalogs, access artifact content,
    or search any global artifact scope.

    Construction enforces the nominal pair only. Message-tree semantics,
    catalog uniqueness, and catalog-local reference resolution remain owned by
    their existing validators and resolvers, which have the complete data needed
    to report stable domain errors.
    """

    document: MessageDocument
    """Complete mapped message document produced from one response fragment."""

    artifacts: ArtifactCatalog
    """Catalog that supplies artifacts belonging to the mapped document result."""

    def __post_init__(self) -> None:
        """Require the complete nominal document and artifact catalog pair."""
        document = cast(object, self.document)
        artifacts = cast(object, self.artifacts)

        # A concrete MessageDocument fixes the root and immutable message-tree
        # storage. Accepting a group or arbitrary structural object would omit
        # version, purpose, metadata, and document-wide validation boundaries.
        if not isinstance(document, MessageDocument):
            raise TypeError("MessageMappingResult document must be a MessageDocument.")

        # Require an explicit catalog even when it is empty. None would conflate
        # a completed mapping with a mapper that forgot to return artifact scope,
        # while a bare tuple would bypass catalog-local validation and resolution.
        if not isinstance(artifacts, ArtifactCatalog):
            raise TypeError(
                "MessageMappingResult artifacts must be an ArtifactCatalog."
            )
