"""HTTP request body bytes, without text decoding."""

from __future__ import annotations

from typing import cast

from mconet.core.spi.transport_body import TransportBody


def map_http_body(body: TransportBody) -> bytes:
    """Return the complete body octets that the system transport will write.

    An empty body is ``b""``. Binary octets, including values that are not
    valid UTF-8, are returned unchanged and are not decoded into text. The
    media type is not read. The function does not add ``Content-Length`` or
    ``Content-Type``, and it does not open a connection.

    Args:
        body: Complete encoded body already held in memory.

    Returns:
        The same byte string stored on ``body``.

    Raises:
        TypeError: If ``body`` or its byte storage has an invalid shape.
    """
    candidate = cast(object, body)
    if not isinstance(candidate, TransportBody):
        raise TypeError("body must be a TransportBody.")

    payload = cast(object, candidate.bytes)
    # Text would hide embedded NULs and invalid UTF-8. Only the original byte
    # string is a request body this transport can write.
    if not isinstance(payload, bytes):
        raise TypeError("TransportBody bytes must be a Bytes value.")
    return payload
