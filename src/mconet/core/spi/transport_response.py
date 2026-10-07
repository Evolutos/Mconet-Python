"""Immutable complete-byte response returned by a transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Bytes
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Combine protocol-neutral response metadata with complete body bytes.

    The selected transport reports classification and wire observations through
    ``response_metadata`` while returning the received payload as immutable
    bytes. This value does not decode content, infer status, or reselect a codec.
    """

    response_metadata: TransportResponseMetadata
    """Normalized outcome and native response facts excluding body content."""

    body: Bytes
    """Complete immutable response octets supplied to the fixed decoder path."""

    def __post_init__(self) -> None:
        """Require established metadata and immutable byte storage."""
        response_metadata = cast(object, self.response_metadata)
        body = cast(object, self.body)

        # Require the complete metadata value so outcome and native protocol
        # facts cannot be replaced by a status integer, mapping, or request data.
        if not isinstance(response_metadata, TransportResponseMetadata):
            raise TypeError(
                "TransportResponse response_metadata must be a "
                "TransportResponseMetadata."
            )

        # Bytes is a static nominal type backed by built-in bytes. The runtime
        # check excludes mutable buffers and request-side TransportBody wrappers.
        if not isinstance(body, bytes):
            raise TypeError("TransportResponse body must be a Bytes value.")
