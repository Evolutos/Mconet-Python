"""Open structural contract for model description data."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class ModelDescriptor(Protocol):
    """Describe a model without restricting providers or naming schemes.

    Implementations must expose the complete read-only field surface. Semantic
    validation is deliberately separate so custom descriptors can preserve
    unknown family identifiers and extension fields without inheriting a base
    class or registering a concrete model type.
    """

    @property
    def name(self) -> str:
        """Return the required provider-facing model name."""
        ...

    @property
    def display_name(self) -> str | None:
        """Return an optional human-readable model label."""
        ...

    @property
    def family(self) -> OpenIdentifier | None:
        """Return an optional open model-family identifier."""
        ...

    @property
    def version(self) -> str | None:
        """Return an optional producer-supplied model version."""
        ...

    @property
    def description(self) -> str | None:
        """Return optional human-readable model information."""
        ...

    @property
    def metadata(self) -> Extensions:
        """Return non-control metadata associated with the model."""
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned fields preserved for forward compatibility."""
        ...
