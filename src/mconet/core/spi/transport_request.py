"""Immutable protocol-neutral request prepared for transport dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Headers, QueryParameters, UriValue
from mconet.core.spi.transport_body import TransportBody


@dataclass(frozen=True, slots=True)
class TransportRequest:
    """Combine the exact method, URL, fields, parameters, and encoded body.

    The request is a transport-ready snapshot. It preserves caller order and
    spelling without validating a protocol-specific method, modifying the URL,
    merging repeated headers or query parameters, or re-encoding the body.
    """

    method: str
    """Protocol method text selected by the request mapper."""

    url: UriValue
    """Structured absolute or relative destination URI reference."""

    headers: Headers
    """Ordered protocol-neutral request header fields."""

    query: QueryParameters
    """Ordered query parameters to append during transport serialization."""

    body: TransportBody
    """Complete encoded body and its representation media type."""

    def __post_init__(self) -> None:
        """Require the established immutable request component types."""
        method = cast(object, self.method)
        url = cast(object, self.url)
        headers = cast(object, self.headers)
        query = cast(object, self.query)
        body = cast(object, self.body)

        # Keep method policy with the concrete transport. This boundary accepts
        # extension methods but never coerces an arbitrary dynamic value to text.
        if not isinstance(method, str):
            raise TypeError("TransportRequest method must be a string.")

        # Retain the URI value and its declared absolute/relative form exactly;
        # syntax validation remains an explicit upstream operation.
        if not isinstance(url, UriValue):
            raise TypeError("TransportRequest url must be a UriValue.")

        # Reuse the immutable collections so repeated fields and parameters keep
        # their caller-defined order through request mapping and serialization.
        if not isinstance(headers, Headers):
            raise TypeError("TransportRequest headers must be Headers.")
        if not isinstance(query, QueryParameters):
            raise TypeError("TransportRequest query must be QueryParameters.")

        # Accept only the completed body value; this request does not guess a
        # media type or introduce unsupported streaming and multipart variants.
        if not isinstance(body, TransportBody):
            raise TypeError("TransportRequest body must be a TransportBody.")
