"""Read-only raw response retained only when a caller opts in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata


@dataclass(frozen=True, slots=True)
class RawResponseSnapshot:
    """Store one response body and its metadata without decoding them.

    Construction is the opt-in. Nothing in this value copies a response by
    itself, selects a decoder, or reads a secret. ``body`` and ``metadata``
    stay read-only after construction.

    The body is the exact byte sequence supplied by the caller. Metadata is
    the transport observation supplied by the caller. This value does not
    trim, redact, or enforce a size cap.
    """

    body: Bytes
    """Complete response octets retained for this opted-in snapshot."""

    metadata: TransportResponseMetadata
    """Response classification and headers retained with the body."""

    def __post_init__(self) -> None:
        """Require immutable body bytes and nominal response metadata."""
        body = cast(object, self.body)
        metadata = cast(object, self.metadata)
        if not isinstance(body, bytes):
            raise TypeError("RawResponseSnapshot body must be a Bytes value.")
        if not isinstance(metadata, TransportResponseMetadata):
            raise TypeError(
                "RawResponseSnapshot metadata must be a TransportResponseMetadata."
            )
