"""Catalog-local resolution tests for immutable ArtifactReference values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactReference,
    ArtifactSource,
    Extensions,
    LocalFileArtifactSource,
    ModelInteractionError,
    OpenIdentifier,
    resolve_artifact_reference,
)


def _empty_mapping() -> Extensions:
    """Create independent portable mapping storage for test artifacts."""
    # Each fixture owns its dictionary so one scenario cannot mutate another and
    # make reference resolution depend on execution order.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a complete open ArtifactKind for resolver fixtures."""

    id: OpenIdentifier
    """Open semantic classification identity."""

    semantic: str | None = None
    """Optional producer guidance."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown portable kind fields."""


@dataclass(frozen=True, slots=True)
class _Source:
    """Provide a custom data-only ArtifactSource."""

    kind: OpenIdentifier
    """Open source representation identity."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Provide one complete structural Artifact resolver target."""

    id: str
    """Identity local to one enclosing catalog."""

    kind: ArtifactKind
    """Open semantic classification."""

    media_type: str | None
    """Optional declared media type."""

    source: ArtifactSource
    """Data-only content origin."""

    descriptor: ArtifactDescriptor | None = None
    """Optional modality facts omitted by default."""

    metadata: ArtifactMetadata = field(default_factory=_empty_mapping)
    """Portable intrinsic artifact data."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown portable Artifact fields."""


class _ObservedBinaryHandle(BytesIO):
    """Track forbidden resolver handle operations."""

    read_calls: int
    seek_calls: int
    close_calls: int

    def __init__(self, value: bytes) -> None:
        """Initialize in-memory bytes and zero every operation counter."""
        # BytesIO supplies standard binary handle identity while counters make
        # accidental content access visible without an external filesystem.
        super().__init__(value)
        self.read_calls = 0
        self.seek_calls = 0
        self.close_calls = 0

    def read(self, size: int | None = -1) -> bytes:
        """Record content access before delegating to the buffer."""
        # A lookup must not probe bytes even when the requested size is zero.
        self.read_calls += 1
        return super().read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        """Record position mutation before delegating to the buffer."""
        # Temporary repositioning would violate caller ownership and is observed.
        self.seek_calls += 1
        return super().seek(offset, whence)

    def close(self) -> None:
        """Record ownership-sensitive closure before releasing the buffer."""
        # The test fixture performs the only expected close after resolution.
        self.close_calls += 1
        super().close()


def _artifact(
    artifact_id: str,
    *,
    source: ArtifactSource | None = None,
    media_type: str | None = "application/octet-stream",
) -> _Artifact:
    """Create one valid Artifact target with explicit field overrides."""
    # Fresh collaborators isolate lookup behavior while an explicit source can
    # carry a caller-owned runtime handle for the no-I/O integration scenario.
    return _Artifact(
        id=artifact_id,
        kind=_Kind(OpenIdentifier("artifact.file")),
        media_type=media_type,
        source=(
            source
            if source is not None
            else _Source(OpenIdentifier("vendor.memory_handle"))
        ),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its message fragment."""
    # Returning the caught object enables normalized field assertions while the
    # narrow boundary prevents unrelated fixture failures from passing.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_reference_resolver_returns_exact_matching_artifact() -> None:
    """Verify ordered lookup returns the original case-sensitive ID match."""
    first = _artifact("item")
    second = _artifact("Item")
    target = _artifact("target")
    catalog = ArtifactCatalog((first, second, target))
    reference = ArtifactReference(
        "target",
        relation=OpenIdentifier("artifact.preview_of"),
        metadata={"preferred": True},
    )

    resolved = resolve_artifact_reference(reference, catalog)

    # Only artifact_id participates in selection. Relation and metadata stay on
    # the reference, and the target is neither copied nor wrapped.
    assert resolved is target
    assert resolved is catalog.artifacts[2]
    assert resolve_artifact_reference(ArtifactReference("item"), catalog) is first
    assert resolve_artifact_reference(ArtifactReference("Item"), catalog) is second
    assert reference.relation == OpenIdentifier("artifact.preview_of")
    assert reference.metadata == {"preferred": True}


def test_reference_resolver_uses_only_the_supplied_catalog_scope() -> None:
    """Verify equal IDs resolve independently in request and result catalogs."""
    request_artifact = _artifact("shared-id")
    result_artifact = _artifact("shared-id")
    request_catalog = ArtifactCatalog((request_artifact,))
    result_catalog = ArtifactCatalog((result_artifact,))
    reference = ArtifactReference("shared-id")

    # Two explicit calls select different identities. No global or session state
    # remembers the first resolution or merges the independent scopes.
    assert resolve_artifact_reference(reference, request_catalog) is request_artifact
    assert resolve_artifact_reference(reference, result_catalog) is result_artifact
    assert request_artifact is not result_artifact


def test_reference_resolver_raises_stable_not_found_error() -> None:
    """Verify an absent ID produces artifact_reference_not_found fields."""
    missing_id = "private-label\nsecond-line"
    reference = ArtifactReference(missing_id)
    catalog = ArtifactCatalog((_artifact("other"),))

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: resolve_artifact_reference(reference, catalog),
            "does not match an artifact",
        ),
    )

    # Portable normalized fields identify the failure without reflecting the raw
    # producer ID or control characters into exception and logging surfaces.
    assert error.category.id == OpenIdentifier("invalid_request")
    assert error.phase.id == OpenIdentifier("artifact_resolution")
    assert error.code == "artifact_reference_not_found"
    assert error.message == (
        "ArtifactReference does not match an artifact in the supplied catalog."
    )
    assert missing_id not in str(error)
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_reference_resolver_treats_empty_id_as_an_unmatched_reference() -> None:
    """Verify an empty stored ID follows the single not-found outcome."""
    reference = ArtifactReference("")

    # ArtifactReference construction preserves exact string storage. Resolution
    # does not invent a null state or a second error code for an unmatched string.
    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: resolve_artifact_reference(reference, ArtifactCatalog()),
            "does not match an artifact",
        ),
    )
    assert error.code == "artifact_reference_not_found"


def test_reference_resolver_rejects_duplicate_catalog_before_lookup() -> None:
    """Verify an ambiguous catalog cannot silently select its first target."""
    first = _artifact("duplicate")
    second = _artifact("duplicate")
    catalog = ArtifactCatalog((first, second))

    # Catalog validation is a mandatory precondition. Its stable duplicate code
    # takes precedence over returning either structurally valid member.
    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: resolve_artifact_reference(ArtifactReference("duplicate"), catalog),
            "artifact IDs must be unique",
        ),
    )
    assert error.code == "duplicate_artifact_id"
    assert error.phase.id == OpenIdentifier("validation")


def test_reference_resolver_composes_complete_catalog_validation() -> None:
    """Verify an invalid non-target member fails before lookup returns a match."""
    invalid = _artifact("invalid", media_type="not-a-media-type")
    target = _artifact("target")
    catalog = ArtifactCatalog((invalid, target))

    # Validation covers the whole supplied scope before searching; otherwise a
    # later match could hide malformed members and make outcomes order-dependent.
    _assert_raises(
        ValueError,
        lambda: resolve_artifact_reference(ArtifactReference("target"), catalog),
        "type/subtype",
    )


def test_reference_resolver_performs_no_source_io() -> None:
    """Verify lookup and composed validation leave target content untouched."""
    handle = _ObservedBinaryHandle(b"artifact-content")
    try:
        target = _artifact(
            "target",
            source=LocalFileArtifactSource(file_handle=handle),
        )
        catalog = ArtifactCatalog((target,))

        # Resolving identity does not imply opening or reading the ArtifactSource.
        assert (
            resolve_artifact_reference(ArtifactReference("target"), catalog) is target
        )
        assert handle.read_calls == 0
        assert handle.seek_calls == 0
        assert handle.close_calls == 0
        assert handle.tell() == 0
        assert not handle.closed
    finally:
        # The fixture remains the sole owner responsible for handle cleanup.
        handle.close()


def test_reference_resolver_rechecks_reference_runtime_types() -> None:
    """Verify arbitrary objects and corrupted IDs fail before catalog access."""
    corrupted = ArtifactReference("target")
    object.__setattr__(corrupted, "artifact_id", 7)
    catalog = ArtifactCatalog((_artifact("target"),))

    # Both failures occur before catalog validation or traversal, providing a
    # deterministic reference-boundary diagnostic without reflective lookup.
    _assert_raises(
        TypeError,
        lambda: resolve_artifact_reference(cast(ArtifactReference, object()), catalog),
        "reference must be an ArtifactReference",
    )
    _assert_raises(
        TypeError,
        lambda: resolve_artifact_reference(corrupted, catalog),
        "artifact_id must be a string",
    )
