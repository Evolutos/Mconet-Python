"""Protocol-neutral asynchronous transport contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_request import TransportRequest
from mconet.core.spi.transport_response import TransportResponse


@runtime_checkable
class Transport(RuntimeComponent, Protocol):
    """Send one frozen request and return one protocol-neutral response.

    Implementations serialize the request through their native transport,
    observe deadline and cancellation controls from the supplied context,
    normalize the native outcome, and return immutable response metadata plus
    complete body bytes.

    The contract deliberately excludes model and message semantics, task
    adapters, payload encoding and decoding, credential acquisition,
    authorization interpretation, request mutation, retry policy, and output
    assembly. Ordinary structural classes can implement it without SDK
    inheritance or a registry entry.
    """

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Send one transport-ready request under one interaction context."""
        # The awaitable boundary covers native network I/O and cancellation. The
        # request is already frozen, so implementations only observe its values.
        ...
