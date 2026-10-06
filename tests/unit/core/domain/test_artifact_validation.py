"""Semantic validation tests for open Artifact implementations."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast

from mconet.core.domain import (
    Artifact,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactSource,
    Bytes,
    Extensions,
    InlineArtifactSource,
    LocalFileArtifactSource,
    OpenIdentifier,
    SecretValue,
    UriArtifactSource,
    UriValue,
    validate_artifact,
)


def _empty_mapping() -> Extensions:
    """Create independent extension storage for structural test fixtures."""
    # Independent dictionaries prevent one negative case from mutating another
    # fixture and making validator results depend on test execution order.
    return {}


@dataclass(frozen=True, slots=True)
class _Kind:
    """Provide a complete open ArtifactKind implementation for tests."""

    id: OpenIdentifier
    """Open semantic classification identity."""

    semantic: str | None = None
    """Optional producer guidance retained without interpretation."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown portable kind fields."""


@dataclass(frozen=True, slots=True)
class _Source:
    """Provide an unknown data-only ArtifactSource implementation."""

    kind: OpenIdentifier
    """Open source representation identity."""


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Provide an unknown ArtifactDescriptor implementation."""

    kind: OpenIdentifier
    """Open descriptor-shape identity."""

    dimensions: int = 3
    """Provider-specific fact left uninterpreted by common validation."""


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Provide opaque Authorization with a secret test credential."""

    kind: OpenIdentifier
    """Open handler-selection identity."""

    credential: SecretValue
    """Secret value that Artifact validation must never inspect."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Complete structural Artifact fixture with replaceable test fields."""

    id: str
    """Catalog-local identity."""

    kind: ArtifactKind
    """Open semantic classification."""

    media_type: str | None
    """Optional declared media type text."""

    source: ArtifactSource
    """Data-only content origin."""

    descriptor: ArtifactDescriptor | None = None
    """Optional modality-specific facts."""

    metadata: ArtifactMetadata = field(default_factory=_empty_mapping)
    """Portable intrinsic artifact data."""

    extensions: Extensions = field(default_factory=_empty_mapping)
    """Unknown portable Artifact fields."""


class _ObservedBinaryHandle(BytesIO):
    """Expose counters for every forbidden validator handle operation."""

    read_calls: int
    seek_calls: int
    close_calls: int

    def __init__(self, value: bytes) -> None:
        """Initialize in-memory content and zero operation counters."""
        # The standard IOBase implementation satisfies BinaryIO storage while
        # counters make accidental validation-time access directly observable.
        super().__init__(value)
        self.read_calls = 0
        self.seek_calls = 0
        self.close_calls = 0

    def read(self, size: int | None = -1) -> bytes:
        """Record a content read before delegating to the buffer."""
        # Even a zero-length probe violates data-only validation, so every call
        # increments before normal BytesIO behavior can occur.
        self.read_calls += 1
        return super().read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        """Record a position change before delegating to the buffer."""
        # A temporary seek followed by restoration is still externally visible
        # and therefore must be detected by the test boundary.
        self.seek_calls += 1
        return super().seek(offset, whence)

    def close(self) -> None:
        """Record closure before releasing the caller-owned buffer."""
        # The fixture performs the only expected close after validation so source
        # ownership mistakes remain distinguishable from deterministic cleanup.
        self.close_calls += 1
        super().close()


class _ReclassifiedInlineSource(InlineArtifactSource):
    """Return a mismatched kind from a nominal inline source."""

    @property
    def kind(self) -> OpenIdentifier:
        """Expose the URI kind to exercise fixed-source identity validation."""
        # The payload remains valid bytes so failure can only come from the
        # concrete representation being reclassified as another source kind.
        return OpenIdentifier("artifact.uri")


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # The narrow boundary prevents an unrelated fixture error from satisfying a
    # specific Artifact contract assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _artifact(**overrides: object) -> _Artifact:
    """Build one valid open Artifact and apply explicit scenario overrides."""
    arguments: dict[str, object] = {
        "id": "artifact-1",
        "kind": _Kind(OpenIdentifier("vendor.depth_map")),
        "media_type": "application/vnd.vendor.depth+binary; version=1",
        "source": _Source(OpenIdentifier("vendor.memory_handle")),
        "descriptor": _Descriptor(OpenIdentifier("vendor.spatial_grid")),
        "metadata": {"width": 640, "height": 480},
        "extensions": {"vendor.calibrated": True},
    }
    # Updating a fresh dictionary centralizes the ordinary valid baseline while
    # ensuring each failure changes only the field under examination.
    arguments.update(overrides)
    return _Artifact(
        id=cast(str, arguments["id"]),
        kind=cast(ArtifactKind, arguments["kind"]),
        media_type=cast(str | None, arguments["media_type"]),
        source=cast(ArtifactSource, arguments["source"]),
        descriptor=cast(ArtifactDescriptor | None, arguments["descriptor"]),
        metadata=cast(ArtifactMetadata, arguments["metadata"]),
        extensions=cast(Extensions, arguments["extensions"]),
    )


def _overwrite_field(artifact: _Artifact, field_name: str, value: object) -> _Artifact:
    """Replace one frozen field to emulate corrupted boundary input."""
    # Untyped deserializers can bypass annotations and frozen assignment. Direct
    # object mutation creates that state without weakening production values.
    object.__setattr__(artifact, field_name, value)
    return artifact


def test_artifact_validator_preserves_valid_open_implementation() -> None:
    """Verify unknown kinds and descriptors pass by identity without rewriting."""
    artifact = _artifact()
    original_kind = artifact.kind
    original_source = artifact.source
    original_descriptor = artifact.descriptor

    validated = validate_artifact(artifact)

    # Identity across every open dimension proves validation performs no known
    # registry lookup, media normalization, wrapping, or capability filtering.
    assert validated is artifact
    assert validated.kind is original_kind
    assert validated.source is original_source
    assert validated.descriptor is original_descriptor
    assert validated.media_type == "application/vnd.vendor.depth+binary; version=1"


def test_artifact_validator_preserves_optional_absence() -> None:
    """Verify absent descriptor, media type, and URI authorization remain valid."""
    source = UriArtifactSource(UriValue("../content/item.bin", False))
    artifact = _artifact(source=source, descriptor=None, media_type=None)

    # None is a deliberate state for all three optional fields. Validation does
    # not invent a descriptor, infer media text, or create authorization input.
    assert validate_artifact(artifact) is artifact
    assert artifact.descriptor is None
    assert artifact.media_type is None
    assert source.authorization is None


def test_artifact_validator_accepts_known_sources_without_access() -> None:
    """Verify inline, URI, path, and handle sources pass without content I/O."""
    authorization = _Authorization(
        OpenIdentifier("authorization.vendor_signature"),
        SecretValue("placeholder-credential"),
    )
    handle = _ObservedBinaryHandle(b"content")
    sources: tuple[ArtifactSource, ...] = (
        InlineArtifactSource(Bytes(b"content")),
        UriArtifactSource(UriValue("../content/item.bin", False), authorization),
        LocalFileArtifactSource(path=Path("../content/item.bin")),
        LocalFileArtifactSource(file_handle=handle),
    )
    try:
        # Each concrete value is revalidated fully, but no source is opened,
        # resolved, downloaded, consumed, repositioned, or closed.
        for source in sources:
            artifact = _artifact(source=source)
            assert validate_artifact(artifact) is artifact
        assert handle.read_calls == 0
        assert handle.seek_calls == 0
        assert handle.close_calls == 0
        assert handle.tell() == 0
        assert not handle.closed
        assert str(authorization.credential) == "[REDACTED]"
    finally:
        # The test retains sole ownership of its runtime file handle.
        handle.close()


def test_artifact_validator_rejects_incomplete_artifact_and_bad_id() -> None:
    """Verify the full protocol and usable catalog-local identity are required."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteArtifact:
        """Intentionally omit optional and JSON Artifact properties."""

        id: str
        """Candidate local identity."""

        kind: ArtifactKind
        """Candidate semantic kind."""

        source: ArtifactSource
        """Candidate source."""

    incomplete = _IncompleteArtifact(
        "artifact-1",
        _Kind(OpenIdentifier("artifact.file")),
        _Source(OpenIdentifier("vendor.memory")),
    )
    # Missing protocol properties fail before field inspection; empty identities
    # then fail independently without being trimmed or normalized.
    _assert_raises(
        TypeError,
        lambda: validate_artifact(cast(Artifact, incomplete)),
        "must implement Artifact",
    )
    _assert_raises(
        TypeError,
        lambda: validate_artifact(_overwrite_field(_artifact(), "id", 7)),
        "id must be a string",
    )
    for artifact_id in ("", " \t"):
        _assert_raises(
            ValueError,
            lambda artifact_id=artifact_id: validate_artifact(
                _artifact(id=artifact_id)
            ),
            "id must not be empty or whitespace",
        )


def test_artifact_validator_checks_open_kind_contract() -> None:
    """Verify kind identity, semantic text, and extensions fail independently."""
    cases: tuple[tuple[ArtifactKind, type[BaseException], str], ...] = (
        (
            cast(ArtifactKind, OpenIdentifier("artifact.file")),
            TypeError,
            "kind must implement ArtifactKind",
        ),
        (
            _Kind(cast(OpenIdentifier, "artifact.file")),
            TypeError,
            "kind id must be an OpenIdentifier",
        ),
        (
            _Kind(OpenIdentifier("Invalid Kind")),
            ValueError,
            "OpenIdentifier",
        ),
        (
            _Kind(OpenIdentifier("artifact.file"), semantic=cast(str, 1)),
            TypeError,
            "kind semantic must be a string or None",
        ),
        (
            _Kind(
                OpenIdentifier("artifact.file"),
                extensions=cast(Extensions, {1: True}),
            ),
            TypeError,
            "kind extensions keys must be strings",
        ),
        (
            _Kind(
                OpenIdentifier("artifact.file"),
                extensions={"unsafe": math.inf},
            ),
            ValueError,
            "must be finite",
        ),
    )

    # Every open-kind field is validated without comparing identity to a closed
    # registry, so only malformed values fail these cases.
    for kind, exception_type, message in cases:
        _assert_raises(
            exception_type,
            lambda kind=kind: validate_artifact(_artifact(kind=kind)),
            message,
        )


def test_artifact_validator_checks_source_identity_and_fixed_kind() -> None:
    """Verify open source identity and concrete representation kind agree."""
    invalid_sources: tuple[tuple[ArtifactSource, type[BaseException], str], ...] = (
        (
            cast(ArtifactSource, object()),
            TypeError,
            "source must implement ArtifactSource",
        ),
        (
            _Source(cast(OpenIdentifier, "vendor.memory")),
            TypeError,
            "source kind must be an OpenIdentifier",
        ),
        (
            _Source(OpenIdentifier("Invalid Source")),
            ValueError,
            "OpenIdentifier",
        ),
        (
            _ReclassifiedInlineSource(Bytes(b"content")),
            ValueError,
            "kind must be artifact.inline",
        ),
    )

    # Unknown portable identifiers remain valid; only malformed identity or a
    # concrete source masquerading as another representation is rejected.
    for source, exception_type, message in invalid_sources:
        _assert_raises(
            exception_type,
            lambda source=source: validate_artifact(_artifact(source=source)),
            message,
        )


def test_artifact_validator_rechecks_known_source_fields() -> None:
    """Verify corrupted concrete source storage cannot bypass construction."""
    inline = InlineArtifactSource(Bytes(b"content"))
    uri_syntax = UriArtifactSource(UriValue("https://example.test/content", True))
    uri_type = UriArtifactSource(UriValue("https://example.test/content", True))
    uri_authorization = UriArtifactSource(
        UriValue("https://example.test/content", True)
    )
    local_text = LocalFileArtifactSource(path=Path("content.bin"))
    local_missing = LocalFileArtifactSource(path=Path("content.bin"))
    local_path_type = LocalFileArtifactSource(path=Path("content.bin"))
    text_handle = StringIO("content")
    try:
        object.__setattr__(inline, "bytes", bytearray(b"mutable"))
        object.__setattr__(uri_syntax, "uri", UriValue("missing-scheme", True))
        object.__setattr__(uri_type, "uri", "https://example.test/content")
        object.__setattr__(uri_authorization, "authorization", object())
        object.__setattr__(local_text, "path", None)
        object.__setattr__(local_text, "file_handle", text_handle)
        object.__setattr__(local_missing, "path", None)
        object.__setattr__(local_path_type, "path", "content.bin")

        # Validators treat frozen values as external boundary input and repeat
        # invariants without reading payloads or probing handle modes.
        cases: tuple[tuple[ArtifactSource, type[BaseException], str], ...] = (
            (inline, TypeError, "bytes must be a Bytes value"),
            (uri_syntax, ValueError, "must contain a valid scheme"),
            (uri_type, TypeError, "uri must be a UriValue"),
            (
                uri_authorization,
                TypeError,
                "authorization must implement Authorization or be None",
            ),
            (local_text, TypeError, "file_handle must be a BinaryIO or None"),
            (
                local_missing,
                ValueError,
                "requires exactly one of path or file_handle",
            ),
            (local_path_type, TypeError, "path must be a Path or None"),
        )
        for source, exception_type, message in cases:
            _assert_raises(
                exception_type,
                lambda source=source: validate_artifact(_artifact(source=source)),
                message,
            )
    finally:
        # The rejected text handle remains caller-owned and is cleaned up here.
        text_handle.close()


def test_artifact_validator_checks_uri_authorization_kind() -> None:
    """Verify URI credentials stay opaque while handler identity is validated."""
    authorization = _Authorization(
        OpenIdentifier("Invalid Authorization"),
        SecretValue("placeholder-credential"),
    )
    source = UriArtifactSource(
        UriValue("https://example.test/content", True),
        authorization,
    )

    # Only the public kind crosses the validator boundary. The credential remains
    # redacted and no handler is selected or invoked by validation.
    _assert_raises(
        ValueError,
        lambda: validate_artifact(_artifact(source=source)),
        "OpenIdentifier",
    )
    assert str(authorization.credential) == "[REDACTED]"


def test_artifact_validator_checks_descriptor_and_media_type() -> None:
    """Verify optional descriptor identity and media syntax remain independent."""
    invalid_cases: tuple[tuple[dict[str, object], type[BaseException], str], ...] = (
        (
            {"descriptor": cast(ArtifactDescriptor, object())},
            TypeError,
            "descriptor must implement ArtifactDescriptor or be None",
        ),
        (
            {"descriptor": _Descriptor(cast(OpenIdentifier, "descriptor.image"))},
            TypeError,
            "descriptor kind must be an OpenIdentifier",
        ),
        (
            {"descriptor": _Descriptor(OpenIdentifier("Invalid Descriptor"))},
            ValueError,
            "OpenIdentifier",
        ),
        ({"media_type": 1}, TypeError, "media_type must be a string or None"),
        ({"media_type": "image"}, ValueError, "type/subtype"),
    )

    # No descriptor registry or Kind-MIME table is invented. Each optional field
    # is checked through its own open syntax contract only.
    for overrides, exception_type, message in invalid_cases:
        _assert_raises(
            exception_type,
            lambda overrides=overrides: validate_artifact(_artifact(**overrides)),
            message,
        )


def test_artifact_validator_checks_metadata_and_extensions() -> None:
    """Verify both JSON mappings enforce keys, shapes, cycles, and number policy."""
    cyclic: list[object] = []
    cyclic.append(cyclic)
    invalid_cases: tuple[tuple[dict[str, object], type[BaseException], str], ...] = (
        ({"metadata": []}, TypeError, "metadata must be a mapping"),
        ({"metadata": {1: True}}, TypeError, "metadata keys must be strings"),
        (
            {"metadata": {"tuple": (1, 2)}},
            TypeError,
            "structurally valid JsonValue",
        ),
        (
            {"extensions": {"cycle": cyclic}},
            TypeError,
            "structurally valid JsonValue",
        ),
        (
            {"extensions": {"unsafe": 2**53}},
            ValueError,
            "safe range",
        ),
    )

    # Mapping channels are checked independently so diagnostics retain the field
    # that crossed the portability boundary with invalid data.
    for overrides, exception_type, message in invalid_cases:
        _assert_raises(
            exception_type,
            lambda overrides=overrides: validate_artifact(_artifact(**overrides)),
            message,
        )
