"""Open descriptive contract for artifact modality properties."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class ArtifactDescriptor(Protocol):
    """Identify a modality-specific artifact description without behavior.

    Concrete descriptors may expose image dimensions, audio sampling facts,
    video timing facts, vector dimensions, or future provider properties. The
    common protocol carries only open description identity: validators and
    transformers own interpretation, compatibility checks, and conversion.
    """

    @property
    def kind(self) -> OpenIdentifier:
        """Return the open identifier classifying this descriptor shape."""
        # Classification selects a descriptive field vocabulary without reading
        # artifact content, validating values, or invoking a transformation.
        ...
