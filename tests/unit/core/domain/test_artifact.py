"""Open structural contract tests for Artifact implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Artifact,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactSource,
    Extensions,
    OpenIdentifier,
)


def _empty_mapping() -> Extensions:
    """Create independent empty JSON storage for test implementation defaults."""
    # Each artifact owns separate metadata and extension mappings so protocol
    # tests never rely on mutable default state shared by dataclass instances.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Custom artifact kind implemented without an SDK base class."""

    id: OpenIdentifier
    """Open semantic classification identity."""

    semantic: str | None = None
    """Optional producer guidance for an unfamiliar classification."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Provider-defined kind fields retained as JSON data."""


@dataclass(frozen=True, slots=True)
class _RuntimeSource:
    """Custom source containing opaque runtime data but no access operation."""

    kind: OpenIdentifier
    """Open source representation identity."""

    handle: object
    """Opaque source state whose interpretation belongs to a future reader."""


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Custom modality descriptor implemented without SDK inheritance."""

    kind: OpenIdentifier
    """Open descriptor-shape identity."""

    dimensions: int
    """Provider-defined modality fact retained without validation."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Immutable custom artifact proving complete structural conformance."""

    id: str
    """Catalog-local artifact identity."""

    kind: ArtifactKind
    """Semantic artifact classification."""

    media_type: str | None
    """Optional declared media type text."""

    source: ArtifactSource
    """Description of the artifact content origin."""

    descriptor: ArtifactDescriptor | None
    """Optional modality-specific descriptive properties."""

    metadata: ArtifactMetadata = field(default_factory=_empty_mapping)
    """Portable descriptive data intrinsic to the artifact."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown versioned artifact fields retained for compatibility."""


def _accept_artifact(artifact: Artifact) -> Artifact:
    """Return a statically accepted artifact without adapting its implementation."""
    # Identity preservation proves structural use needs neither SDK inheritance,
    # a concrete wrapper, nor a central artifact-type registry.
    return artifact


def test_artifact_keeps_every_shared_dimension_independent() -> None:
    """Verify identity, kind, media, source, descriptor, and JSON data stay separate."""
    kind = _Kind(
        id=OpenIdentifier("vendor.depth_map"),
        semantic="Depth values aligned to an image plane.",
    )
    handle = object()
    source = _RuntimeSource(OpenIdentifier("vendor.memory_handle"), handle)
    descriptor = _Descriptor(OpenIdentifier("vendor.spatial_grid"), 3)
    artifact = _Artifact(
        id="depth-1",
        kind=kind,
        media_type="application/vnd.vendor.depth+binary",
        source=source,
        descriptor=descriptor,
        metadata={"width": 640, "height": 480},
        extensions={"vendor.calibrated": True},
    )

    # No field is derived from another: open semantic and representation IDs,
    # raw media text, opaque source state, modality facts, and JSON channels stay.
    accepted = _accept_artifact(artifact)
    assert isinstance(artifact, Artifact)
    assert accepted is artifact
    assert accepted.id == "depth-1"
    assert accepted.kind is kind
    assert accepted.media_type == "application/vnd.vendor.depth+binary"
    assert accepted.source is source
    assert source.handle is handle
    assert accepted.descriptor is descriptor
    assert descriptor.dimensions == 3
    assert accepted.metadata == {"width": 640, "height": 480}
    assert accepted.extensions == {"vendor.calibrated": True}


def test_artifact_preserves_absent_optional_descriptions() -> None:
    """Verify media type and modality descriptor can independently remain absent."""
    artifact = _Artifact(
        id="opaque-1",
        kind=_Kind(OpenIdentifier("artifact.unknown")),
        media_type=None,
        source=_RuntimeSource(OpenIdentifier("vendor.opaque_handle"), object()),
        descriptor=None,
    )

    # None is not replaced by an empty media string or generic descriptor; both
    # optional facts remain distinct from an unknown semantic artifact kind.
    assert isinstance(artifact, Artifact)
    assert artifact.media_type is None
    assert artifact.descriptor is None
    assert artifact.kind.id == OpenIdentifier("artifact.unknown")
    assert artifact.metadata == {}
    assert artifact.extensions == {}


def test_artifact_protocol_declares_only_descriptive_shared_fields() -> None:
    """Verify the common contract contains exact data fields and no operations."""
    declared_properties = {
        name for name, value in vars(Artifact).items() if isinstance(value, property)
    }
    declared_operations = {
        name
        for name, value in vars(Artifact).items()
        if not name.startswith("_") and callable(value)
    }

    # Exact surface checks keep validation, reading, resolution, upload, and
    # transformation behavior out of the shared immutable description.
    assert declared_properties == {
        "id",
        "kind",
        "media_type",
        "source",
        "descriptor",
        "metadata",
        "extensions",
    }
    assert declared_operations == set()


def test_artifact_requires_the_complete_shared_surface() -> None:
    """Verify artifact-like values cannot omit optional or JSON field properties."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteArtifact:
        """Intentionally expose only identity, kind, and source."""

        id: str
        """Candidate Catalog-local identity."""

        kind: ArtifactKind
        """Candidate semantic classification."""

        source: ArtifactSource
        """Candidate source without remaining shared fields."""

    candidate = _IncompleteArtifact(
        id="incomplete",
        kind=_Kind(OpenIdentifier("vendor.incomplete")),
        source=_RuntimeSource(OpenIdentifier("vendor.inline"), object()),
    )

    # Optional values may be None and mappings may be empty, but every property
    # must exist so consumers need no reflection or concrete-type branching.
    assert not isinstance(candidate, Artifact)
    assert not isinstance(cast(object, candidate.kind), Artifact)
