"""Ordered local-scope tests for immutable ArtifactCatalog values."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field
from typing import cast

from mconet.core.domain import (
    Artifact,
    ArtifactCatalog,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactReference,
    ArtifactSource,
    Extensions,
    OpenIdentifier,
)


def _empty_mapping() -> Extensions:
    """Create independent empty JSON storage for custom artifact values."""
    # Separate mappings avoid shared mutable defaults while keeping Catalog tests
    # focused on collection ownership rather than concrete Artifact construction.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Minimal open ArtifactKind implementation for Catalog members."""

    id: OpenIdentifier
    """Open semantic classification identity."""

    semantic: str | None = None
    """Optional meaning for a provider-defined kind."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Provider kind fields retained as JSON data."""


@dataclass(frozen=True, slots=True)
class _Source:
    """Minimal descriptive ArtifactSource implementation for Catalog members."""

    kind: OpenIdentifier
    """Open source representation identity."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Complete immutable Artifact implementation used by Catalog tests."""

    id: str
    """Identity local to one enclosing Catalog."""

    kind: ArtifactKind
    """Open semantic classification."""

    media_type: str | None
    """Optional declared media type text."""

    source: ArtifactSource
    """Data-only content origin description."""

    descriptor: ArtifactDescriptor | None = None
    """Optional modality descriptor omitted by these fixtures."""

    metadata: ArtifactMetadata = field(default_factory=_empty_mapping)
    """Portable descriptive Artifact data."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown versioned Artifact fields."""


def _artifact(artifact_id: str) -> _Artifact:
    """Create one complete custom Artifact with the supplied local ID."""
    # Every call creates independent structural collaborators so ordering and
    # identity assertions cannot pass because fixtures accidentally share state.
    return _Artifact(
        id=artifact_id,
        kind=_Kind(OpenIdentifier("artifact.file")),
        media_type="application/octet-stream",
        source=_Source(OpenIdentifier("vendor.memory_blob")),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow exception boundary prevents an unrelated construction failure
    # from satisfying the exact Catalog storage assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_artifact_catalog_uses_an_explicit_empty_collection() -> None:
    """Verify no artifacts is an immutable empty tuple rather than null."""
    catalog = ArtifactCatalog()

    # A concrete empty collection remains immediately iterable and distinguishable
    # from missing or unresolved Catalog state in every call path.
    assert catalog.artifacts == ()
    assert isinstance(catalog.artifacts, tuple)
    assert catalog.artifacts is not None


def test_artifact_catalog_preserves_member_order_and_identity() -> None:
    """Verify ordered Artifact membership is retained without adaptation."""
    first = _artifact("first")
    second = _artifact("second")
    catalog = ArtifactCatalog((first, second))

    # Tuple order is part of the value, and structural Artifacts enter unchanged
    # rather than being wrapped in SDK concrete implementations.
    assert catalog.artifacts == (first, second)
    assert catalog.artifacts[0] is first
    assert catalog.artifacts[1] is second
    assert all(isinstance(artifact, Artifact) for artifact in catalog.artifacts)


def test_artifact_catalog_localizes_reference_scope() -> None:
    """Verify identical IDs can exist independently in separate Catalogs."""
    request_artifact = _artifact("shared-id")
    result_artifact = _artifact("shared-id")
    request_catalog = ArtifactCatalog((request_artifact,))
    result_catalog = ArtifactCatalog((result_artifact,))
    reference = ArtifactReference("shared-id")

    # The bare Reference carries no global Catalog identity. A later resolver must
    # receive one enclosing Catalog explicitly, so equal IDs do not merge scopes.
    assert request_catalog.artifacts[0] is request_artifact
    assert result_catalog.artifacts[0] is result_artifact
    assert request_catalog.artifacts[0] is not result_catalog.artifacts[0]
    assert reference.artifact_id == request_artifact.id == result_artifact.id


def test_artifact_catalog_defers_duplicate_id_validation() -> None:
    """Verify construction preserves duplicate evidence for the later validator."""
    first = _artifact("duplicate")
    second = _artifact("duplicate")
    catalog = ArtifactCatalog((first, second))

    # Definition owns collection shape only. Silently dropping or overwriting a
    # duplicate would prevent the dedicated validator returning its stable error.
    assert catalog.artifacts == (first, second)
    assert len(catalog.artifacts) == 2
    assert tuple(artifact.id for artifact in catalog.artifacts) == (
        "duplicate",
        "duplicate",
    )


def test_artifact_catalog_is_immutable_and_has_no_lookup_behavior() -> None:
    """Verify Catalog owns membership but does not resolve ArtifactReference."""
    catalog = ArtifactCatalog((_artifact("artifact-1"),))
    parameters = tuple(inspect.signature(ArtifactCatalog).parameters)

    # Frozen tuple storage prevents replacement or append operations, while the
    # one-field constructor and absent lookup methods keep Resolver work separate.
    assert parameters == ("artifacts",)
    assert not hasattr(catalog, "resolve")
    assert not hasattr(catalog, "get")
    _assert_raises(
        FrozenInstanceError,
        lambda: catalog.__setattr__("artifacts", ()),
        "cannot assign to field",
    )


def test_artifact_catalog_rejects_invalid_storage_and_members() -> None:
    """Verify dynamic callers cannot use null, lists, or non-Artifact members."""
    # Reject alternate collection shapes first, then verify every tuple member
    # exposes the complete Artifact protocol before it enters the local scope.
    for value in (None, [], [_artifact("artifact-1")]):
        _assert_raises(
            TypeError,
            lambda value=value: ArtifactCatalog(cast(tuple[Artifact, ...], value)),
            "artifacts must be a tuple",
        )
    _assert_raises(
        TypeError,
        lambda: ArtifactCatalog(cast(tuple[Artifact, ...], ("artifact",))),
        "must contain Artifact values",
    )
