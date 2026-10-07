"""Reusable asynchronous assertions for Transport implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.spi import (
    ComponentDescriptor,
    Transport,
    TransportContext,
    TransportRequest,
    TransportResponse,
)

_ValueT = TypeVar("_ValueT")


class TransportContractSuite:
    """Apply reusable request, response, failure, and cancellation contracts.

    The suite is independent of pytest, unittest, fixture formats, and concrete
    network protocols. Callers provide complete immutable requests and contexts,
    then inspect exact responses, failures, or cancellation errors through
    synchronous callbacks. Transport and callback failures remain unwrapped so
    the owning test framework retains its normal diagnostics.

    Runtime checks supplement static protocol conformance: component metadata
    and successful responses must use their nominal public SDK types, and
    ``send`` must expose the asynchronous SPI boundary. Each assertion dispatches
    exactly once and performs no request mutation, native serialization, network
    setup, response decoding, retry, deadline calculation, logging, or output
    assembly.
    """

    __slots__ = ("_transport",)

    def __init__(self, transport: Transport) -> None:
        """Validate and retain one structurally conforming async transport.

        Args:
            transport: Custom or SDK transport subjected to reusable cases.

        Raises:
            TypeError: If the object, descriptor, or send operation violates the
                public asynchronous transport boundary.
        """
        transport_value = cast(object, transport)
        if not isinstance(transport_value, Transport):
            raise TypeError("transport must implement Transport.")
        descriptor_value = cast(object, transport.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("transport descriptor must be a ComponentDescriptor.")

        # Transport is the asynchronous I/O boundary. Accept an async bound
        # method or callable object, but reject synchronous look-alike methods.
        send = transport.send
        if not (iscoroutinefunction(send) or iscoroutinefunction(type(send).__call__)):
            raise TypeError("transport send operation must be asynchronous.")
        self._transport = transport

    async def assert_send(
        self,
        request: TransportRequest,
        context: TransportContext,
        *,
        assertion: Callable[[TransportResponse], None],
    ) -> None:
        """Validate one successful dispatch with a caller assertion.

        Args:
            request: Exact frozen request supplied by the contract case.
            context: Exact interaction controls supplied for the dispatch.
            assertion: Synchronous callback asserting response facts.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the transport returns no TransportResponse.
            BaseException: Any exact transport or assertion callback failure.
        """
        checked_assertion = _validate_callback(assertion, name="assertion")

        # Await one direct invocation so request/context identities and every
        # unexpected transport exception remain observable without translation.
        actual = await self._transport.send(request, context)
        actual_value = cast(object, actual)
        if not isinstance(actual_value, TransportResponse):
            raise AssertionError("transport must return a TransportResponse.")
        checked_assertion(actual_value)

    async def assert_send_failure(
        self,
        request: TransportRequest,
        context: TransportContext,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require a non-cancellation transport failure and expose it exactly.

        Args:
            request: Exact frozen request supplied by the negative case.
            context: Exact interaction controls supplied for the dispatch.
            assertion: Synchronous callback asserting failure facts and identity.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the transport completes successfully.
            asyncio.CancelledError: Any cancellation, kept separate from errors.
            BaseException: Any exact assertion callback failure.
        """
        checked_assertion = _validate_callback(assertion, name="assertion")

        try:
            await self._transport.send(request, context)
        except asyncio.CancelledError:
            # Cancellation has a dedicated assertion path and must retain normal
            # task propagation when this method is itself externally cancelled.
            raise
        except BaseException as error:
            captured_error = error
        else:
            raise AssertionError("transport was expected to fail.")

        # Invoke outside the catch block so a callback failure is never confused
        # with or wrapped as the transport failure supplied to that callback.
        checked_assertion(captured_error)

    async def assert_send_cancellation(
        self,
        request: TransportRequest,
        context: TransportContext,
        *,
        cancel: Callable[[], None],
        assertion: Callable[[asyncio.CancelledError], None],
    ) -> None:
        """Trigger active context cancellation during one pending dispatch.

        Args:
            request: Exact frozen request supplied by the cancellation case.
            context: Context carrying one present, initially active signal.
            cancel: Synchronous operation applying cancellation to that signal.
            assertion: Synchronous callback asserting cancellation facts.

        Raises:
            TypeError: If context or either callback has an invalid shape.
            ValueError: If the context has no signal or is already cancelled.
            AssertionError: If dispatch completes before cancellation, the cancel
                operation does not transition the context signal, or the
                transport completes successfully after cancellation.
            asyncio.CancelledError: If the contract-case task itself is cancelled.
            BaseException: Any exact transport, cancel, or callback failure.
        """
        context_value = cast(object, context)
        if not isinstance(context_value, TransportContext):
            raise TypeError("context must be a TransportContext.")
        checked_cancel = _validate_zero_callback(cancel, name="cancel")
        checked_assertion = _validate_callback(assertion, name="assertion")

        signal = context.cancellation
        if signal is None:
            raise ValueError("context cancellation must be present.")
        if signal.is_cancelled:
            raise ValueError("context cancellation must be active before dispatch.")

        # A task lets the transport enter its async boundary before the caller's
        # signal control fires. A later signal check also covers transports that
        # subscribe after this first event-loop opportunity.
        send_task = asyncio.create_task(self._transport.send(request, context))
        await asyncio.sleep(0)
        if send_task.done():
            try:
                await send_task
            except BaseException:
                # Preserve any early transport failure or cancellation exactly;
                # it did not result from the requested in-flight transition.
                raise
            raise AssertionError("transport completed before cancellation.")

        try:
            checked_cancel()
        except BaseException:
            # A bad trigger must not leave transport I/O running after this
            # contract assertion exits with the trigger's exact failure.
            await _cancel_and_settle(send_task)
            raise

        if not signal.is_cancelled:
            await _cancel_and_settle(send_task)
            raise AssertionError("cancel must transition the context signal.")

        try:
            await send_task
        except asyncio.CancelledError as error:
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                # Cancellation requested on this assertion task is caller-owned,
                # not evidence that the transport observed the context signal.
                raise
            checked_assertion(error)
            return
        raise AssertionError("transport was expected to cancel.")


def _validate_callback(
    callback: Callable[[_ValueT], None],
    *,
    name: str,
) -> Callable[[_ValueT], None]:
    """Require one named synchronous callable before transport dispatch."""
    callback_value = cast(object, callback)
    if not callable(callback_value):
        raise TypeError(f"{name} must be callable.")
    if iscoroutinefunction(callback) or iscoroutinefunction(type(callback).__call__):
        # Async callbacks would not execute their body in this synchronous
        # callback slot and would leave an unawaited coroutine behind.
        raise TypeError(f"{name} must be synchronous.")
    return callback


def _validate_zero_callback(
    callback: Callable[[], None],
    *,
    name: str,
) -> Callable[[], None]:
    """Require one named zero-argument synchronous callable."""
    callback_value = cast(object, callback)
    if not callable(callback_value):
        raise TypeError(f"{name} must be callable.")
    if iscoroutinefunction(callback) or iscoroutinefunction(type(callback).__call__):
        # The cancellation trigger is invoked synchronously after dispatch; an
        # async callable would never transition the context signal in that slot.
        raise TypeError(f"{name} must be synchronous.")
    return callback


async def _cancel_and_settle(task: asyncio.Task[TransportResponse]) -> None:
    """Cancel one internal send task and consume its terminal outcome."""
    if not task.done():
        # Cancellation prevents a failed case setup from leaking background I/O
        # or retaining its request, context, and cancellation subscriptions.
        task.cancel()
    try:
        await task
    except BaseException:
        # Cleanup outcomes are intentionally secondary to the original callback
        # or setup failure that required this private cancellation path.
        pass
