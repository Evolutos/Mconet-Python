"""Monitor-visible request view after authorization has been applied."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.headers import Headers
from mconet.core.runtime.pre_authorization_snapshot import (
    omitted_authorization_header_names,
)
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.transport_request import TransportRequest


def request_view_for_monitor(
    request: TransportRequest,
    authorization: Authorization,
) -> TransportRequest:
    """Return an immutable request view that omits authorization fields.

    Ordinary monitors receive this view, not the open mutation window. A
    ``MutableTransportRequest`` is rejected before its headers are read. The
    returned view drops ``Authorization`` and a decision's configured header
    name. Credential sources are not called.

    Args:
        request: Immutable request produced after authorization.
        authorization: Decision whose header name is omitted when present.

    Returns:
        A new immutable request with ordinary fields preserved.

    Raises:
        TypeError: If ``request`` is still mutable, or if either argument has
            the wrong nominal type.
    """
    candidate = cast(object, request)
    # Reject the open window before touching its fields. Those fields can hold
    # the credential that authorization just wrote.
    if isinstance(candidate, MutableTransportRequest):
        raise TypeError("A monitor cannot read a MutableTransportRequest.")
    if not isinstance(candidate, TransportRequest):
        raise TypeError("request must be a TransportRequest.")
    authorization_value = cast(object, authorization)
    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")

    omitted = omitted_authorization_header_names(authorization_value)
    retained = tuple(
        field
        for field in candidate.headers.values
        if field.name.casefold() not in omitted
    )
    return TransportRequest(
        method=candidate.method,
        url=candidate.url,
        headers=Headers(retained),
        query=candidate.query,
        body=candidate.body,
    )
