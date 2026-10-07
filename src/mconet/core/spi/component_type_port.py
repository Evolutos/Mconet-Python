"""Immutable type metadata for one runtime component port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import MediaType, OpenIdentifier


@dataclass(frozen=True, slots=True)
class ComponentTypePort:
    """Describe the value contract exposed by one named component port.

    Field values are preserved exactly so component resolution can compare
    explicit contracts without inferring schemas or media types. Port direction
    belongs to the containing component contract rather than this value object.
    """

    name: str
    """Stable port name within its containing component contract."""

    type_id: OpenIdentifier
    """Language-neutral identifier for values carried by the port."""

    schema_id: str | None = None
    """Optional schema identifier used for structural compatibility checks."""

    media_type: MediaType | None = None
    """Optional structured media type used for representation compatibility."""

    def __post_init__(self) -> None:
        """Require the declared immutable field shapes without normalization."""
        name = cast(object, self.name)
        type_id = cast(object, self.type_id)
        schema_id = cast(object, self.schema_id)
        media_type = cast(object, self.media_type)

        # Preserve producer-defined strings exactly. Semantic compatibility is
        # evaluated when adjacent component contracts are connected, while this
        # boundary prevents dynamically typed callers from changing field kinds.
        if not isinstance(name, str):
            raise TypeError("ComponentTypePort name must be a string.")
        if not isinstance(type_id, OpenIdentifier):
            raise TypeError("ComponentTypePort type_id must be an OpenIdentifier.")
        if schema_id is not None and not isinstance(schema_id, str):
            raise TypeError("ComponentTypePort schema_id must be a string or None.")
        if media_type is not None and not isinstance(media_type, MediaType):
            raise TypeError("ComponentTypePort media_type must be a MediaType or None.")
