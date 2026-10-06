"""Catalog-local validation tests for immutable ArtifactCatalog values."""

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
    ArtifactSource,
    Extensions,
    LocalFileArtifactSource,
    ModelInteractionError,
    OpenIdentifier,
    validate_artifact_catalog,
)


def _empty_mapping() -> Extensions:
    """Create independent portable mapping storage for test artifacts."""
    # Each fixture owns its dictionary so a negative case cannot mutate shared
    # state and make uniqueness results depend on test execution order.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a complete open ArtifactKind for catalog members."""

    id: OpenIdentifier
    """Open semantic classification identity."""

    semantic: str | None = None
    """Optional producer guidance."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown portable kind fields."""


@dataclass(frozen=True, slots=True)
class _Source:
    """Provide a data-only custom ArtifactSource for ordinary fixtures."""

    kind: OpenIdentifier
    """Open source representation identity."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Provide one complete structural Artifact catalog member."""

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
    """Track forbidden catalog-validation handle operations."""

    read_calls: int
    seek_calls: int
    close_calls: int

    def __init__(self, value: bytes) -> None:
        """Initialize an in-memory binary handle and zero operation counters."""
        # BytesIO supplies standard binary IO identity while the counters expose
        # any accidental member-validation access without touching a real file.
        super().__init__(value)
        self.read_calls = 0
        self.seek_calls = 0
        self.close_calls = 0

    def read(self, size: int | None = -1) -> bytes:
        """Record a content read before delegating to the buffer."""
        # Catalog validation must never reach content, including zero-byte probes.
        self.read_calls += 1
        return super().read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        """Record a position change before delegating to the buffer."""
        # Temporary repositioning is still externally observable and forbidden.
        self.seek_calls += 1
        return super().seek(offset, whence)

    def close(self) -> None:
        """Record ownership-sensitive closure before releasing the buffer."""
        # The test performs exactly one close after catalog validation finishes.
        self.close_calls += 1
        super().close()


def _artifact(
    artifact_id: str,
    *,
    source: ArtifactSource | None = None,
    media_type: str | None = "application/octet-stream",
) -> _Artifact:
    """Create one valid Artifact with explicit local identity and overrides."""
    # Fresh collaborators keep member validation independent while allowing a
    # caller-owned runtime source to exercise the no-I/O composition boundary.
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
    # Returning the exact instance lets normalized error fields be asserted while
    # a narrow boundary prevents unrelated fixture failures from passing.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_artifact_catalog_validator_accepts_empty_and_unique_catalogs() -> None:
    """Verify empty and ordered unique members pass without replacement."""
    empty = ArtifactCatalog()
    first = _artifact("first")
    second = _artifact("second")
    catalog = ArtifactCatalog((first, second))

    # Successful validation preserves catalog identity, tuple identity, order,
    # and member identity rather than rebuilding or sorting the collection.
    assert validate_artifact_catalog(empty) is empty
    assert validate_artifact_catalog(catalog) is catalog
    assert catalog.artifacts == (first, second)
    assert catalog.artifacts[0] is first
    assert catalog.artifacts[1] is second


def test_artifact_catalog_validator_raises_stable_duplicate_error() -> None:
    """Verify equal IDs return the normalized duplicate_artifact_id failure."""
    duplicate_id = "private-label\nsecond-line"
    catalog = ArtifactCatalog(
        (_artifact(duplicate_id), _artifact("other"), _artifact(duplicate_id))
    )

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_artifact_catalog(catalog),
            "artifact IDs must be unique",
        ),
    )

    # Stable normalized fields are portable across SDKs. The raw producer ID is
    # deliberately absent from message text to avoid control-character injection.
    assert error.category.id == OpenIdentifier("invalid_request")
    assert error.phase.id == OpenIdentifier("validation")
    assert error.code == "duplicate_artifact_id"
    assert error.message == "ArtifactCatalog artifact IDs must be unique."
    assert duplicate_id not in str(error)
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_artifact_catalog_validator_scopes_ids_to_one_catalog() -> None:
    """Verify identical IDs remain legal in independent request/result scopes."""
    request_artifact = _artifact("shared-id")
    result_artifact = _artifact("shared-id")
    request_catalog = ArtifactCatalog((request_artifact,))
    result_catalog = ArtifactCatalog((result_artifact,))

    # No global registry or process state links two calls. Each invocation creates
    # a fresh local set and therefore preserves independent request/result scope.
    assert validate_artifact_catalog(request_catalog) is request_catalog
    assert validate_artifact_catalog(result_catalog) is result_catalog
    assert request_artifact is not result_artifact


def test_artifact_catalog_validator_composes_artifact_validation() -> None:
    """Verify malformed members fail before duplicate comparison can hide them."""
    first = _artifact("duplicate")
    invalid = _artifact("duplicate", media_type="not-a-media-type")
    catalog = ArtifactCatalog((first, invalid))

    # The second member is validated before its ID enters duplicate detection, so
    # a malformed Artifact cannot be reported merely as a duplicate identifier.
    _assert_raises(
        ValueError,
        lambda: validate_artifact_catalog(catalog),
        "type/subtype",
    )


def test_artifact_catalog_validator_performs_no_source_io() -> None:
    """Verify composed Artifact validation leaves runtime handles untouched."""
    handle = _ObservedBinaryHandle(b"artifact-content")
    try:
        source = LocalFileArtifactSource(file_handle=handle)
        catalog = ArtifactCatalog((_artifact("file-1", source=source),))

        # Catalog membership and ID checks never consume, reposition, or own the
        # handle while validating its member through validate_artifact().
        assert validate_artifact_catalog(catalog) is catalog
        assert handle.read_calls == 0
        assert handle.seek_calls == 0
        assert handle.close_calls == 0
        assert handle.tell() == 0
        assert not handle.closed
    finally:
        # The fixture remains the sole owner responsible for cleanup.
        handle.close()


def test_artifact_catalog_validator_rechecks_runtime_storage() -> None:
    """Verify dynamic corruption cannot bypass nominal Catalog construction."""
    non_tuple = ArtifactCatalog()
    invalid_member = ArtifactCatalog()
    object.__setattr__(non_tuple, "artifacts", [])
    object.__setattr__(invalid_member, "artifacts", ("artifact",))

    # External deserializers or untyped code may bypass frozen construction, so
    # the validator repeats container and member boundaries deterministically.
    _assert_raises(
        TypeError,
        lambda: validate_artifact_catalog(cast(ArtifactCatalog, object())),
        "catalog must be an ArtifactCatalog",
    )
    _assert_raises(
        TypeError,
        lambda: validate_artifact_catalog(non_tuple),
        "artifacts must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: validate_artifact_catalog(invalid_member),
        "artifacts must contain Artifact values",
    )
