"""Execution-scope tests for empty artifact catalogs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from typing import cast
from unittest.mock import patch

from mconet.core.domain import (
    ArtifactCatalog,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactSource,
    Extensions,
    LocalFileArtifactSource,
    ModelInteractionError,
    OpenIdentifier,
    validate_empty_artifact_catalog_scope,
)


def _empty_extensions() -> Extensions:
    """Create independent portable mapping storage for test artifacts."""
    # A fresh dictionary prevents one fixture from changing another scenario's
    # metadata or extensions through shared mutable defaults.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a complete open ArtifactKind for scope fixtures."""

    id: OpenIdentifier
    """Open semantic classification identity."""

    semantic: str | None = None
    """Optional producer guidance."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable Kind fields."""


@dataclass(frozen=True, slots=True)
class _Source:
    """Provide a data-only custom ArtifactSource for ordinary fixtures."""

    kind: OpenIdentifier
    """Open source representation identity."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Provide one complete structural Artifact catalog member."""

    id: str
    """Identity local to one enclosing Catalog."""

    kind: ArtifactKind
    """Open semantic classification."""

    media_type: str | None
    """Optional declared media type."""

    source: ArtifactSource
    """Data-only content origin."""

    descriptor: ArtifactDescriptor | None = None
    """Optional modality facts omitted by default."""

    metadata: ArtifactMetadata = field(default_factory=_empty_extensions)
    """Portable intrinsic Artifact data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable Artifact fields."""


class _ObservedBinaryHandle(BytesIO):
    """Track every forbidden scope-check handle operation."""

    read_calls: int
    seek_calls: int
    close_calls: int

    def __init__(self, value: bytes) -> None:
        """Initialize in-memory bytes and zero all operation counters."""
        # BytesIO supplies a standard binary handle while counters make any
        # accidental access visible without touching an external filesystem.
        super().__init__(value)
        self.read_calls = 0
        self.seek_calls = 0
        self.close_calls = 0

    def read(self, size: int | None = -1) -> bytes:
        """Record a read before delegating to the in-memory handle."""
        # Even a zero-byte probe violates the data-only validation boundary.
        self.read_calls += 1
        return super().read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        """Record a position change before delegating to the handle."""
        # Temporary repositioning is externally visible even if later restored.
        self.seek_calls += 1
        return super().seek(offset, whence)

    def close(self) -> None:
        """Record closure before releasing the caller-owned buffer."""
        # The fixture performs the only expected close during final cleanup.
        self.close_calls += 1
        super().close()


def _artifact(
    artifact_id: str,
    *,
    source: ArtifactSource | None = None,
    media_type: str | None = "application/octet-stream",
) -> _Artifact:
    """Create one valid Artifact with explicit scenario overrides."""
    # Fresh collaborators keep scenarios isolated while allowing a caller-owned
    # source to exercise zero-I/O behavior through composed validation.
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
    # A narrow boundary ensures an unrelated fixture failure cannot satisfy a
    # specific domain-ordering or support-policy assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_empty_artifact_catalog_scope_accepts_only_explicit_empty_catalog() -> None:
    """Verify a validated empty tuple passes without replacement."""
    catalog = ArtifactCatalog()
    original_artifacts = catalog.artifacts

    # Identity proves the gate does not create a replacement Catalog or sentinel;
    # tuple identity proves it does not rebuild even the explicit empty value.
    assert validate_empty_artifact_catalog_scope(catalog) is catalog
    assert catalog.artifacts is original_artifacts
    assert catalog.artifacts == ()


def test_empty_artifact_catalog_scope_rejects_nonempty_catalog_stably() -> None:
    """Verify one valid member returns the normalized support failure."""
    private_id = "private-artifact\nsecond-line"
    artifact = _artifact(private_id)
    catalog = ArtifactCatalog((artifact,))

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_empty_artifact_catalog_scope(catalog),
            "Only an empty ArtifactCatalog is supported",
        ),
    )

    # Stable fields remain portable while untrusted member identity, Kind, source,
    # and count are deliberately absent from exception text.
    assert error.category.id == OpenIdentifier("unsupported_feature")
    assert error.phase.id == OpenIdentifier("validation")
    assert error.code == "unsupported_message_content"
    assert error.message == "Only an empty ArtifactCatalog is supported."
    assert private_id not in str(error)
    assert "artifact.file" not in str(error)
    assert "vendor.memory_handle" not in str(error)
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_empty_artifact_catalog_scope_preserves_duplicate_error_precedence() -> None:
    """Verify duplicate IDs fail before the non-empty support policy."""
    duplicate_id = "private-duplicate\nsecond-line"
    catalog = ArtifactCatalog((_artifact(duplicate_id), _artifact(duplicate_id)))

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_empty_artifact_catalog_scope(catalog),
            "artifact IDs must be unique",
        ),
    )

    # Complete Catalog validation remains the sole owner of uniqueness and its
    # stable error instead of being shadowed by the later scope decision.
    assert error.category.id == OpenIdentifier("invalid_request")
    assert error.phase.id == OpenIdentifier("validation")
    assert error.code == "duplicate_artifact_id"
    assert duplicate_id not in str(error)


def test_empty_artifact_catalog_scope_preserves_artifact_validation() -> None:
    """Verify malformed members fail before the non-empty support policy."""
    invalid = _artifact("artifact-1", media_type="not-a-media-type")
    catalog = ArtifactCatalog((invalid,))

    # Media syntax is a domain invariant, so the dedicated Artifact validator's
    # precise failure remains observable instead of unsupported_message_content.
    _assert_raises(
        ValueError,
        lambda: validate_empty_artifact_catalog_scope(catalog),
        "type/subtype",
    )


def test_empty_artifact_catalog_scope_performs_no_source_io() -> None:
    """Verify a rejected local-file Artifact leaves its handle untouched."""
    handle = _ObservedBinaryHandle(b"artifact-content")
    try:
        source = LocalFileArtifactSource(file_handle=handle)
        catalog = ArtifactCatalog((_artifact("file-1", source=source),))

        # Both composed Artifact validation and the support rejection inspect only
        # descriptive fields; neither takes ownership or probes content.
        _assert_raises(
            ModelInteractionError,
            lambda: validate_empty_artifact_catalog_scope(catalog),
            "Only an empty ArtifactCatalog is supported",
        )
        assert handle.read_calls == 0
        assert handle.seek_calls == 0
        assert handle.close_calls == 0
        assert handle.tell() == 0
        assert not handle.closed
    finally:
        # The test remains the sole owner responsible for deterministic cleanup.
        handle.close()

    assert handle.close_calls == 1
    assert handle.closed


def test_empty_artifact_catalog_scope_rechecks_post_validation_storage() -> None:
    """Verify a post-validation container replacement fails safely."""
    catalog = ArtifactCatalog()
    object.__setattr__(catalog, "artifacts", [_artifact("injected")])

    # Replace only the completed validator call to model mutation in the narrow
    # interval before the scope gate consumes the returned Catalog storage.
    with patch(
        "mconet.core.domain.artifact_catalog_scope.validate_artifact_catalog",
        return_value=catalog,
    ):
        _assert_raises(
            TypeError,
            lambda: validate_empty_artifact_catalog_scope(catalog),
            "artifacts must be a tuple",
        )


def test_empty_artifact_catalog_scope_requires_a_valid_catalog_boundary() -> None:
    """Verify nominal input and corrupted storage fail before scope policy."""
    corrupted = ArtifactCatalog()
    object.__setattr__(corrupted, "artifacts", ("not-an-artifact",))

    # The composed Catalog validator owns both nominal identity and member shape;
    # no truthiness shortcut may turn either failure into an unsupported feature.
    _assert_raises(
        TypeError,
        lambda: validate_empty_artifact_catalog_scope(cast(ArtifactCatalog, object())),
        "catalog must be an ArtifactCatalog",
    )
    _assert_raises(
        TypeError,
        lambda: validate_empty_artifact_catalog_scope(corrupted),
        "artifacts must contain Artifact values",
    )
