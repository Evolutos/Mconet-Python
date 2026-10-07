"""Immutable criteria used to resolve one payload decoder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import MediaType


@dataclass(frozen=True, slots=True)
class DecoderSelection:
    """Describe planned media type and schema without naming a decoder.

    Success, error, and event paths each carry their own selection and resolve a
    unique decoder before network I/O. Actual response metadata may later verify
    compatibility, but it never mutates this value or replaces the fixed decoder.
    """

    media_type: MediaType | None = None
    """Optional planned representation type required from the decoder."""

    schema_id: str | None = None
    """Optional schema identity required by the decoded payload contract."""

    def __post_init__(self) -> None:
        """Require optional structured media type and primitive schema text."""
        media_type = cast(object, self.media_type)
        schema_id = cast(object, self.schema_id)

        # Consume an already structured plan value rather than parsing a response
        # Content-Type or inferring a decoder from bytes after network I/O.
        if media_type is not None and not isinstance(media_type, MediaType):
            raise TypeError("DecoderSelection media_type must be a MediaType or None.")

        # Keep schema identity exact and open. Syntax and compatibility checks
        # belong to the execution plan and deterministic component resolver.
        if schema_id is not None and not isinstance(schema_id, str):
            raise TypeError("DecoderSelection schema_id must be a string or None.")
