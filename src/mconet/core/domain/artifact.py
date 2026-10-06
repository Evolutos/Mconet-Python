"""Open structural contract for immutable artifact descriptions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.artifact_descriptor import ArtifactDescriptor
from mconet.core.domain.artifact_kind import ArtifactKind
from mconet.core.domain.artifact_metadata import ArtifactMetadata
from mconet.core.domain.artifact_source import ArtifactSource
from mconet.core.domain.extensions import Extensions


@runtime_checkable
class Artifact(Protocol):
    """Describe artifact identity, representation, origin, and metadata.

    Shared fields stay independent so a kind never implies a source, descriptor,
    media type, or identifier. Implementations may carry runtime-only source data
    such as stream or file handles; readers, validators, resolvers, uploaders, and
    transformers own all behavior outside this descriptive contract.
    """

    @property
    def id(self) -> str:
        """Return the identifier local to the enclosing ArtifactCatalog."""
        # Catalog validation owns uniqueness; this protocol only exposes the
        # producer-supplied identity without deriving it from kind or position.
        ...

    @property
    def kind(self) -> ArtifactKind:
        """Return the open semantic classification of this artifact."""
        # Kind remains independent from media type and source representation so
        # new semantic categories do not require coupled transport changes.
        ...

    @property
    def media_type(self) -> str | None:
        """Return the optional declared media type text."""
        # Raw text is descriptive at this boundary; parsing, normalization, and
        # agreement with kind or descriptor belong to artifact validation.
        ...

    @property
    def source(self) -> ArtifactSource:
        """Return the data-only description of content origin."""
        # Observing a source must not open, read, fetch, upload, or transform its
        # content; explicit runtime components perform those operations later.
        ...

    @property
    def descriptor(self) -> ArtifactDescriptor | None:
        """Return optional modality-specific descriptive properties."""
        # Absence remains valid for artifacts without modality facts, while a
        # present descriptor never substitutes for kind or media type.
        ...

    @property
    def metadata(self) -> ArtifactMetadata:
        """Return read-only, portable metadata intrinsic to the artifact."""
        # Metadata contains descriptive JSON data only and remains distinct from
        # provider extension fields and source-specific state.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned artifact fields for forward compatibility."""
        # Older consumers retain provider data without interpreting it as kind,
        # source, descriptor, media type, or executable behavior.
        ...
