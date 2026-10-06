"""Open descriptive contract for artifact source identity."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class ArtifactSource(Protocol):
    """Identify where artifact content originates without accessing it.

    Concrete sources may describe inline bytes, streams, URIs, local files,
    provider resources, external objects, or future provider-defined origins.
    This protocol intentionally exposes identity only: readers, uploaders, and
    resolvers own every operation that can open, fetch, transfer, or transform
    content.
    """

    @property
    def kind(self) -> OpenIdentifier:
        """Return the open identifier classifying this source representation."""
        # An open identifier enables future source descriptions without adding
        # Core branches; it does not authorize or perform access to the content.
        ...
