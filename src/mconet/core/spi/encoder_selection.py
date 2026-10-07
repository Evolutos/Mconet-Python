"""Immutable criteria used to resolve one payload encoder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import MediaType


@dataclass(frozen=True, slots=True)
class EncoderSelection:
    """Describe media type and schema criteria without naming a component.

    Either criterion may be absent. Candidate discovery, type-contract checks,
    capability matching, and ambiguity handling belong to the component resolver;
    this value only preserves the protocol plan's requested encoding facts.
    """

    media_type: MediaType | None = None
    """Optional structured representation type required from the encoder."""

    schema_id: str | None = None
    """Optional schema identity required by the encoded payload contract."""

    def __post_init__(self) -> None:
        """Require optional structured media type and primitive schema text."""
        media_type = cast(object, self.media_type)
        schema_id = cast(object, self.schema_id)

        # Require an already structured value so selection never reparses a raw
        # Content-Type string or guesses media information from a payload.
        if media_type is not None and not isinstance(media_type, MediaType):
            raise TypeError("EncoderSelection media_type must be a MediaType or None.")

        # Preserve schema identity exactly. Syntax and compatibility are owned by
        # the protocol plan and type-contract resolver rather than this container.
        if schema_id is not None and not isinstance(schema_id, str):
            raise TypeError("EncoderSelection schema_id must be a string or None.")
