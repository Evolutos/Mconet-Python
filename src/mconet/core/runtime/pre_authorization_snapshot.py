"""Credential-free request snapshot taken before authorization is applied."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.headers import Headers
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.transport_request import TransportRequest

# The bearer scheme always uses this field. Comparison is case-insensitive so
# a differently spelled copy cannot remain in a monitor-visible snapshot.
_AUTHORIZATION_HEADER_NAME = "authorization"


def snapshot_pre_authorization_request(
    request: MutableTransportRequest,
    authorization: Authorization,
) -> TransportRequest:
    """Copy the open request without credentials or authorization headers.

    The copy keeps the method, URL, query, body, and ordinary headers. It drops
    every ``Authorization`` field. A decision that names one header, such as a
    header API key, also drops that field. The authorization object itself is
    not stored. Credential sources are not called, and the open request is not
    frozen.

    Args:
        request: Encoded request before an authorization handler changes it.
        authorization: Opaque decision whose header name is omitted when present.

    Returns:
        An immutable request snapshot that monitors can retain.

    Raises:
        TypeError: If ``request`` or ``authorization`` has the wrong nominal type.
    """
    request_value = cast(object, request)
    authorization_value = cast(object, authorization)
    if not isinstance(request_value, MutableTransportRequest):
        raise TypeError("request must be a MutableTransportRequest.")
    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")

    omitted = _omitted_header_names(authorization_value)
    retained = tuple(
        field
        for field in request_value.headers.values
        if field.name.casefold() not in omitted
    )
    return TransportRequest(
        method=request_value.method,
        url=request_value.url,
        headers=Headers(retained),
        query=request_value.query,
        body=request_value.body,
    )


def _omitted_header_names(authorization: Authorization) -> frozenset[str]:
    """Return header names that would carry a credential for this decision."""
    names = {_AUTHORIZATION_HEADER_NAME}
    # Read the configured name only. Resolving the decision would pull a
    # credential into the snapshot that exists to exclude one.
    header_name = cast(object, getattr(authorization, "header_name", None))
    if type(header_name) is str:
        names.add(header_name.casefold())
    return frozenset(names)
