"""Immutable ordered scope for artifacts owned by one request or result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.artifact import Artifact


@dataclass(frozen=True, slots=True)
class ArtifactCatalog:
    """Own an ordered artifact collection as one reference-resolution scope.

    An empty catalog is represented by an empty tuple rather than ``None`` so
    callers never conflate no artifacts with unresolved catalog state. Artifact
    ID uniqueness and reference lookup require dedicated validators and resolvers;
    construction preserves order and supplied IDs without performing either.
    """

    artifacts: tuple[Artifact, ...] = ()
    """Ordered artifacts available within this catalog-local scope."""

    def __post_init__(self) -> None:
        """Require immutable tuple storage containing only Artifact values."""
        artifacts = cast(object, self.artifacts)
        # A tuple fixes membership and order after construction; lists and null
        # cannot become alternate empty-state representations across platforms.
        if not isinstance(artifacts, tuple):
            raise TypeError("ArtifactCatalog artifacts must be a tuple.")

        # Structural membership is checked without invoking Artifact validation.
        # Duplicate IDs and field semantics remain visible to their later gates.
        for artifact in cast(tuple[object, ...], artifacts):
            if not isinstance(artifact, Artifact):
                raise TypeError(
                    "ArtifactCatalog artifacts must contain Artifact values."
                )
