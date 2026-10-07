"""Immutable complete-byte request body supported by the current runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Bytes, MediaType


@dataclass(frozen=True, slots=True)
class TransportBody:
    """Carry one complete encoded byte body and its declared media type.

    The current runtime exposes only an in-memory Bytes representation. Empty,
    streaming, and multipart variants are not constructible placeholders; they
    require their own ownership, repeatability, framing, and signing semantics
    before a future compatible API can add them.
    """

    bytes: Bytes
    """Complete immutable octets ready for authorization and transport."""

    media_type: MediaType
    """Structured representation media type declared by the encoder plan."""

    def __post_init__(self) -> None:
        """Require immutable byte storage and structured media type metadata."""
        body_bytes = cast(object, self.bytes)
        media_type = cast(object, self.media_type)

        # Bytes is a static nominal type backed by built-in bytes. The runtime
        # check prevents mutable buffers or text from entering a frozen body.
        if not isinstance(body_bytes, bytes):
            raise TypeError("TransportBody bytes must be a Bytes value.")

        # Require the existing structured value rather than parsing or guessing
        # a media type from payload contents, file extensions, or headers.
        if not isinstance(media_type, MediaType):
            raise TypeError("TransportBody media_type must be a MediaType.")
