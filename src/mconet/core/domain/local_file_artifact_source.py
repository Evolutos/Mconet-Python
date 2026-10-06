"""Immutable local path or binary handle source for artifact content."""

from __future__ import annotations

from dataclasses import dataclass
from io import IOBase, TextIOBase
from pathlib import Path
from typing import BinaryIO, cast

from mconet.core.domain.open_identifier import OpenIdentifier

_LOCAL_FILE_ARTIFACT_SOURCE_KIND = OpenIdentifier("artifact.local_file")


@dataclass(frozen=True, slots=True)
class LocalFileArtifactSource:
    """Describe artifact content by one local path or open binary handle.

    The source preserves a caller-owned locator without checking the filesystem
    or reading from the handle. A later ArtifactReader owns access, error policy,
    and handle-lifecycle decisions; this value never opens or closes resources.
    """

    path: Path | None = None
    """Optional immutable local filesystem path retained without resolution."""

    file_handle: BinaryIO | None = None
    """Optional caller-owned binary handle retained without any I/O."""

    def __post_init__(self) -> None:
        """Require exactly one supported local locator representation."""
        path = cast(object, self.path)
        file_handle = cast(object, self.file_handle)

        # A concrete source must identify one representation unambiguously;
        # neither missing data nor competing locators can describe one origin.
        if (path is None) == (file_handle is None):
            raise ValueError(
                "LocalFileArtifactSource requires exactly one of path or file_handle."
            )

        # Paths remain lexical values. Requiring Path prevents implicit string
        # conversion while deliberately avoiding exists, stat, or resolve calls.
        if path is not None and not isinstance(path, Path):
            raise TypeError("LocalFileArtifactSource path must be a Path or None.")

        # IOBase recognizes standard Python file objects without invoking read,
        # seek, fileno, or closed. Excluding TextIOBase rejects known text handles;
        # no content probe is used to classify custom binary implementations.
        if file_handle is not None and (
            not isinstance(file_handle, IOBase) or isinstance(file_handle, TextIOBase)
        ):
            raise TypeError(
                "LocalFileArtifactSource file_handle must be a BinaryIO or None."
            )

    @property
    def kind(self) -> OpenIdentifier:
        """Return the standard open identifier for local-file artifact content."""
        # The immutable identifier distinguishes source representation from the
        # artifact.file semantic kind and performs no filesystem interaction.
        return _LOCAL_FILE_ARTIFACT_SOURCE_KIND
