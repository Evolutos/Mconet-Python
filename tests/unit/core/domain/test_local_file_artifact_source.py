"""Tests for immutable local-file artifact sources."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from io import BytesIO, StringIO
from pathlib import Path
from typing import BinaryIO, cast

from mconet.core.domain import (
    ArtifactSource,
    LocalFileArtifactSource,
    OpenIdentifier,
)


class _ObservedBinaryHandle(BytesIO):
    """Track forbidden handle operations without touching external files."""

    read_calls: int
    seek_calls: int
    close_calls: int

    def __init__(self, value: bytes) -> None:
        """Initialize in-memory content and zero every operation counter."""
        # BytesIO provides standard IOBase identity, while explicit counters make
        # every access attempt observable without relying on an actual filesystem.
        super().__init__(value)
        self.read_calls = 0
        self.seek_calls = 0
        self.close_calls = 0

    def read(self, size: int | None = -1) -> bytes:
        """Record a read before delegating to the in-memory handle."""
        # The override is a test tripwire: source construction must leave this
        # counter untouched because even a zero-length probe violates the contract.
        self.read_calls += 1
        return super().read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        """Record a position change before delegating to the handle."""
        # Source construction must not inspect content by changing position and
        # then restoring it, since the temporary mutation is externally visible.
        self.seek_calls += 1
        return super().seek(offset, whence)

    def close(self) -> None:
        """Record ownership-sensitive closure before releasing the buffer."""
        # Explicit cleanup in the test is distinguishable from an unexpected
        # source-side close, proving the value does not take handle ownership.
        self.close_calls += 1
        super().close()


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # A narrow boundary ensures a different setup or I/O failure cannot satisfy
    # a representation-invariant assertion accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_local_file_artifact_source_preserves_lexical_path() -> None:
    """Verify a possibly nonexistent relative path is retained unchanged."""
    path = Path("../unresolved/asset.bin")
    source = LocalFileArtifactSource(path=path)

    # No resolve, absolute conversion, existence check, or path normalization is
    # needed to describe the local locator for a later reader.
    assert source.path is path
    assert source.path == Path("../unresolved/asset.bin")
    assert source.file_handle is None


def test_local_file_artifact_source_retains_handle_without_io() -> None:
    """Verify handle construction performs no reads, seeks, or ownership change."""
    handle = _ObservedBinaryHandle(b"artifact-content")
    try:
        source = LocalFileArtifactSource(file_handle=handle)

        # Identity retention lets the later reader apply its own lifecycle policy.
        # Zero counters prove the value neither probes nor closes caller state.
        assert source.path is None
        assert source.file_handle is handle
        assert handle.read_calls == 0
        assert handle.seek_calls == 0
        assert handle.close_calls == 0
        assert handle.tell() == 0
        assert not handle.closed
    finally:
        # The fixture, not the source, owns deterministic resource cleanup.
        handle.close()

    assert handle.close_calls == 1
    assert handle.closed


def test_local_file_artifact_source_has_standard_source_identity() -> None:
    """Verify path and handle forms share one stable ArtifactSource kind."""
    handle = _ObservedBinaryHandle(b"")
    try:
        path_source = LocalFileArtifactSource(path=Path("asset.bin"))
        handle_source = LocalFileArtifactSource(file_handle=handle)

        # Representation classification is independent of which local locator
        # variant is supplied and never reuses the artifact.file semantic kind.
        assert isinstance(path_source, ArtifactSource)
        assert isinstance(handle_source, ArtifactSource)
        assert path_source.kind == OpenIdentifier("artifact.local_file")
        assert handle_source.kind == path_source.kind
        assert handle_source.kind is path_source.kind
    finally:
        # The test remains the sole owner of its in-memory binary handle.
        handle.close()


def test_local_file_artifact_source_requires_exactly_one_locator() -> None:
    """Verify missing and competing local representations are rejected."""
    handle = _ObservedBinaryHandle(b"")
    try:
        # Both invalid shapes are ambiguous before any ArtifactReader is chosen,
        # so construction rejects them without inspecting either locator.
        _assert_raises(
            ValueError,
            LocalFileArtifactSource,
            "requires exactly one of path or file_handle",
        )
        _assert_raises(
            ValueError,
            lambda: LocalFileArtifactSource(path=Path("asset.bin"), file_handle=handle),
            "requires exactly one of path or file_handle",
        )
        assert handle.read_calls == 0
        assert handle.seek_calls == 0
        assert handle.close_calls == 0
    finally:
        # Cleanup occurs after observing that failed construction took no ownership.
        handle.close()


def test_local_file_artifact_source_is_frozen_and_data_only() -> None:
    """Verify constructor shape, immutability, and absence of access methods."""
    source = LocalFileArtifactSource(path=Path("asset.bin"))
    parameters = inspect.signature(LocalFileArtifactSource).parameters

    # The public constructor exposes only the two locator alternatives. Explicit
    # absence checks prevent later convenience behavior from hiding file I/O.
    assert tuple(parameters) == ("path", "file_handle")
    assert parameters["path"].default is None
    assert parameters["file_handle"].default is None
    for operation in ("read", "open", "stat", "resolve", "seek", "close"):
        assert not hasattr(source, operation)
    _assert_raises(
        FrozenInstanceError,
        lambda: source.__setattr__("path", Path("replacement.bin")),
        "cannot assign to field",
    )


def test_local_file_artifact_source_rejects_invalid_storage_types() -> None:
    """Verify dynamic callers cannot substitute invalid locator representations."""
    text_handle = StringIO()

    # The SDK requires an immutable Path and a standard IOBase-backed handle;
    # implicit conversion or duck-typed probing could itself execute user code.
    try:
        _assert_raises(
            TypeError,
            lambda: LocalFileArtifactSource(path=cast(Path, "asset.bin")),
            "path must be a Path or None",
        )
        _assert_raises(
            TypeError,
            lambda: LocalFileArtifactSource(file_handle=cast(BinaryIO, object())),
            "file_handle must be a BinaryIO or None",
        )
        _assert_raises(
            TypeError,
            lambda: LocalFileArtifactSource(file_handle=cast(BinaryIO, text_handle)),
            "file_handle must be a BinaryIO or None",
        )
    finally:
        # The test retains ownership of the rejected text handle and closes it.
        text_handle.close()
