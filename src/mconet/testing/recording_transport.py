"""Transparent recording decorator for transport contract tests."""

from __future__ import annotations

from typing import cast

from mconet.core.spi import (
    ComponentDescriptor,
    Transport,
    TransportContext,
    TransportRequest,
    TransportResponse,
)


class RecordingTransport:
    """Record exact dispatch inputs before forwarding to another transport.

    The decorator structurally implements ``Transport`` without SDK inheritance.
    Every :meth:`send` appends the exact immutable ``TransportRequest`` and
    ``TransportContext`` pair before awaiting the wrapped transport. Successful,
    failed, and cancelled dispatch attempts therefore remain observable.

    Calls are exposed in invocation order as fresh immutable tuple snapshots.
    Each nested tuple preserves request and context identities, allowing tests to
    assert method, URL, headers, query, body, limits, deadline, cancellation, and
    extensions without this recorder copying or interpreting those values.

    The wrapped transport remains the sole owner of response, failure, delay,
    cancellation, and network behavior. This decorator performs no mutation,
    serialization, retry, decoding, generic component-order recording, reset, or
    dynamic reconfiguration.
    """

    __slots__ = ("_calls", "_descriptor", "_transport")

    def __init__(self, transport: Transport) -> None:
        """Validate and retain the exact transport to decorate.

        Args:
            transport: Complete structural transport receiving forwarded calls.

        Raises:
            TypeError: If the object does not implement ``Transport`` or expose
                a valid ``ComponentDescriptor``.
        """
        transport_value = cast(object, transport)

        # Fail before recording begins so an incomplete delegate cannot produce
        # misleading call evidence that no valid transport could consume.
        if not isinstance(transport_value, Transport):
            raise TypeError("transport must implement Transport.")
        descriptor_value = cast(object, transport.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("transport descriptor must be a ComponentDescriptor.")

        self._transport = transport
        self._descriptor = transport.descriptor
        self._calls: list[tuple[TransportRequest, TransportContext]] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact component metadata exposed by the wrapped transport."""
        # The decorator represents the selected component metadata observed at
        # construction rather than inventing a second descriptor or allowing a
        # malformed mutable delegate to change this contract after validation.
        return self._descriptor

    @property
    def calls(self) -> tuple[tuple[TransportRequest, TransportContext], ...]:
        """Return an immutable snapshot of paired dispatch inputs in call order."""
        # A fresh outer tuple freezes current membership. Inner tuples and both
        # established input values retain exact identity without mutable wrappers.
        return tuple(self._calls)

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record exact inputs and transparently await the wrapped transport.

        Args:
            request: Complete immutable request to retain and forward unchanged.
            context: Exact interaction context to retain and forward unchanged.

        Returns:
            The exact response returned by the wrapped transport.

        Raises:
            TypeError: If a dynamic caller supplies an invalid request or context.
            BaseException: Any failure raised by the wrapped transport, unchanged.
        """
        request_value = cast(object, request)
        context_value = cast(object, context)
        if not isinstance(request_value, TransportRequest):
            raise TypeError("request must be a TransportRequest.")
        if not isinstance(context_value, TransportContext):
            raise TypeError("context must be a TransportContext.")

        # Record before invoking the delegate so synchronous coroutine entry,
        # asynchronous failure, and cancellation attempts are all observable.
        self._calls.append((request, context))

        # Forward both identities unchanged and return or propagate the delegate
        # outcome without wrapping, translating, decoding, or retrying it.
        return await self._transport.send(request, context)
