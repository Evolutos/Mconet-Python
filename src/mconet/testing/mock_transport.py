"""Configurable asynchronous transport test double."""

from __future__ import annotations

import asyncio
from typing import cast

from mconet.core.domain import CancellationSignal, Duration
from mconet.core.spi import (
    ComponentDescriptor,
    TransportContext,
    TransportRequest,
    TransportResponse,
)

_ZERO_DELAY = Duration(0)


class MockTransport:
    """Return, fail, delay, or observe cancellation without network I/O.

    The mock structurally implements ``Transport`` without SDK inheritance.
    Every :meth:`send` waits for one fixed non-negative delay, unless the
    context's cancellation signal is already cancelled or becomes cancelled
    while waiting. A completed wait then raises the exact configured failure or
    returns the exact configured ``TransportResponse``.

    Cancellation is translated to ``asyncio.CancelledError`` with the signal's
    optional reason. The temporary subscription is always removed after return,
    configured failure, signal cancellation, or task cancellation. Response and
    failure identities are preserved; neither is copied, wrapped, or normalized.

    This test double performs no network I/O, request serialization, deadline
    calculation, response decoding, retry, logging, or request recording.
    Dispatch assertions belong to ``RecordingTransport``. Configuration is
    fixed at construction and no reset or dynamic reconfiguration API exists.
    """

    __slots__ = ("_delay", "_descriptor", "_error", "_response")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        response: TransportResponse,
        *,
        error: BaseException | None = None,
        delay: Duration = _ZERO_DELAY,
    ) -> None:
        """Validate and retain one deterministic transport outcome.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            response: Exact response returned when no failure or cancellation wins.
            error: Optional exact failure raised after the configured delay.
            delay: Non-negative duration before evaluating the fixed outcome.

        Raises:
            TypeError: If metadata, response, failure, or delay has an invalid
                nominal type.
            ValueError: If the configured delay is negative.
        """
        descriptor_value = cast(object, descriptor)
        response_value = cast(object, response)
        error_value = cast(object, error)
        delay_value = cast(object, delay)

        # Reject malformed fixture setup before an asynchronous dispatch begins;
        # delayed failures should represent the scenario, not invalid config.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(response_value, TransportResponse):
            raise TypeError("response must be a TransportResponse.")
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")
        if not isinstance(delay_value, Duration):
            raise TypeError("delay must be a Duration.")
        if delay.total_nanoseconds < 0:
            raise ValueError("delay must not be negative.")

        self._descriptor = descriptor
        self._response = response
        self._error = error
        self._delay = delay

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after transport selection or dispatch begins.
        return self._descriptor

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Wait under cancellation, then return or raise the configured outcome.

        Args:
            request: Complete immutable request accepted without interpretation.
            context: Interaction controls supplying optional cancellation state.

        Returns:
            The exact configured ``TransportResponse``.

        Raises:
            TypeError: If a dynamic caller supplies an invalid request or context.
            asyncio.CancelledError: If context cancellation wins the operation.
            BaseException: The exact configured transport failure, when present.
        """
        request_value = cast(object, request)
        context_value = cast(object, context)
        if not isinstance(request_value, TransportRequest):
            raise TypeError("request must be a TransportRequest.")
        if not isinstance(context_value, TransportContext):
            raise TypeError("context must be a TransportContext.")

        # The request has crossed its complete nominal boundary, but this mock
        # deliberately neither serializes nor records it. Only controls matter.
        del request
        await _wait_for_delay(self._delay, context.cancellation)

        if self._error is not None:
            # Preserve failure identity, fields, and control-flow class instead
            # of translating it into a response or generic transport exception.
            raise self._error
        return self._response


async def _wait_for_delay(
    delay: Duration,
    cancellation: CancellationSignal | None,
) -> None:
    """Wait for the configured delay while allowing signal cancellation to win."""
    if cancellation is None:
        # Even zero delay yields once, preserving a genuine asynchronous boundary
        # without creating a subscription or relying on external I/O.
        await asyncio.sleep(delay.total_nanoseconds / 1_000_000_000)
        return

    # Reject pre-cancelled work before creating a sleep task or transport effect.
    if cancellation.is_cancelled:
        raise _cancelled_error(cancellation.reason)

    loop = asyncio.get_running_loop()
    cancelled: asyncio.Future[str | None] = loop.create_future()

    def on_cancel(reason: str | None) -> None:
        """Schedule thread-safe delivery of the signal's first cancellation."""
        # CancellationSignal permits implementation-owned synchronization, so
        # marshal callback delivery onto the send coroutine's event loop.
        loop.call_soon_threadsafe(_complete_cancellation, cancelled, reason)

    unsubscribe = cancellation.subscribe(on_cancel)
    sleep_task = asyncio.create_task(
        asyncio.sleep(delay.total_nanoseconds / 1_000_000_000)
    )
    try:
        # Wait for exactly one terminal condition. A simultaneous signal is
        # checked again below so cancellation wins over a configured outcome.
        await asyncio.wait(
            (sleep_task, cancelled),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if cancelled.done():
            raise _cancelled_error(cancelled.result())
        if cancellation.is_cancelled:
            raise _cancelled_error(cancellation.reason)
    finally:
        # Remove a pending callback and settle the internal sleep on every exit,
        # including external task cancellation and configured signal failure.
        unsubscribe()
        if not sleep_task.done():
            sleep_task.cancel()
        if not cancelled.done():
            # Prevent a successful delay from retaining a permanently pending
            # internal Future; a queued late callback observes done and no-ops.
            cancelled.cancel()
        await _settle_cancelled_sleep(sleep_task)


def _complete_cancellation(
    future: asyncio.Future[str | None],
    reason: str | None,
) -> None:
    """Complete the cancellation future once on its owning event loop."""
    if not future.done():
        # The protocol guarantees first-cancellation stability; the guard also
        # prevents a late queued callback from replacing an existing outcome.
        future.set_result(reason)


async def _settle_cancelled_sleep(sleep_task: asyncio.Task[None]) -> None:
    """Consume internal sleep completion without hiding caller cancellation."""
    try:
        await sleep_task
    except asyncio.CancelledError:
        # Cancellation here belongs only to the private delay task; the outer
        # send coroutine retains its independent result or cancellation state.
        pass


def _cancelled_error(reason: str | None) -> asyncio.CancelledError:
    """Create a cancellation exception preserving an optional signal reason."""
    # An absent reason remains argument-free rather than becoming the text
    # "None", while a supplied reason is observable through standard args.
    if reason is None:
        return asyncio.CancelledError()
    return asyncio.CancelledError(reason)
