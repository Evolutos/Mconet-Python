"""Open structural contract for artifact kind identity and semantics."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class ArtifactKind(Protocol):
    """Describe a standard or provider-defined artifact classification.

    Identity remains open so new modalities and provider resource types do not
    require a Core enumeration change. Optional semantic guidance and extension
    data stay separate from the identifier, allowing an older implementation to
    preserve an unknown kind without claiming that it can process its content.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this artifact kind."""
        # Standard and provider-defined kinds use the same nominal value object;
        # capability support must be determined separately from classification.
        ...

    @property
    def semantic(self) -> str | None:
        """Return optional producer guidance about the kind's meaning."""
        # Descriptive text supplements unknown identity without replacing it or
        # becoming an executable media conversion or dispatch instruction.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return versioned kind data retained for forward compatibility."""
        # Consumers may observe provider JSON, but interpretation and recursive
        # validation belong to later artifact validation and adapter boundaries.
        ...
