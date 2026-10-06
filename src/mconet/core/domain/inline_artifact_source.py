"""Immutable inline byte source for artifact content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.open_identifier import OpenIdentifier

_INLINE_ARTIFACT_SOURCE_KIND = OpenIdentifier("artifact.inline")


@dataclass(frozen=True, slots=True)
class InlineArtifactSource:
    """Describe artifact content carried directly as immutable bytes.

    The value owns no reader, stream, locator, or transfer operation. Consumers
    that need to inspect or move the content must do so through a separate
    artifact behavior contract, keeping this source a side-effect-free value.
    """

    bytes: Bytes
    """Immutable artifact content available without external I/O."""

    def __post_init__(self) -> None:
        """Require the runtime representation promised by the nominal type."""
        value = cast(object, self.bytes)
        # ``Bytes`` is a static nominal type backed by built-in ``bytes``. This
        # runtime guard prevents dynamic callers from retaining mutable buffers
        # or values that only resemble byte content inside the frozen source.
        if not isinstance(value, bytes):
            raise TypeError("InlineArtifactSource bytes must be a Bytes value.")

    @property
    def kind(self) -> OpenIdentifier:
        """Return the standard open identifier for inline artifact content."""
        # The shared identifier is itself immutable, so returning it directly
        # cannot expose mutable class state or trigger source resolution work.
        return _INLINE_ARTIFACT_SOURCE_KIND
