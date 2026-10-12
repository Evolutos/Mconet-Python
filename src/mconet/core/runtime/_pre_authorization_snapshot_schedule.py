"""Runtime scheduling for the pre-authorization monitor snapshot."""

from __future__ import annotations

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.bytes_value import Bytes
from mconet.core.runtime.pre_authorization_snapshot import (
    snapshot_pre_authorization_request,
)
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.transport_body import TransportBody
from mconet.core.spi.transport_request import TransportRequest


def create_pre_authorization_snapshot(
    request: MutableTransportRequest,
    authorization: Authorization,
) -> TransportRequest:
    """Copy the encoded request without secrets, auth headers, or body bytes.

    Header redaction uses the existing pre-authorization snapshot, which drops
    ``Authorization`` and a decision's configured header name. This schedule
    then replaces the body with an empty body of the same media type, so a
    monitor cannot retain the encoded payload. The open request is not frozen
    or modified, and no credential source or authorization handler is called.

    Args:
        request: Encoded request before an authorization handler changes it.
        authorization: Opaque decision whose header name is omitted when present.

    Returns:
        An immutable snapshot safe to retain before authorization.

    Raises:
        TypeError: If ``request`` or ``authorization`` has the wrong nominal type.
    """
    # The existing snapshot removes authorization fields and does not read a
    # credential. It still carries the encoded body, which this stage must not
    # publish.
    redacted = snapshot_pre_authorization_request(request, authorization)
    media_type = redacted.body.media_type
    return TransportRequest(
        method=redacted.method,
        url=redacted.url,
        headers=redacted.headers,
        query=redacted.query,
        body=TransportBody(Bytes(b""), media_type),
    )
