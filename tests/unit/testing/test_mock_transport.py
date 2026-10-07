"""Outcome, delay, and cancellation tests for MockTransport."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import (
    Bytes,
    Duration,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    UriValue,
)
from mconet.core.spi import (
    ComponentDescriptor,
    Transport,
    TransportBody,
    TransportContext,
    TransportOutcome,
    TransportRequest,
    TransportResponse,
    TransportResponseMetadata,
)
from mconet.testing import MockTransport

_ZERO_DELAY = Duration(0)


class _ControllableSignal:
    """Provide externally controlled cancellation for transport tests."""

    def __init__(self) -> None:
        """Create active state with an empty callback collection."""
        # Integer keys make each remover independent while the count exposes
        # whether MockTransport cleans up its temporary subscription.
        self._next_key = 0
        self._callbacks: dict[int, Callable[[str | None], None]] = {}
        self._is_cancelled = False
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether the first cancellation has occurred."""
        # Reading state is passive and does not acknowledge the transition.
        return self._is_cancelled

    @property
    def reason(self) -> str | None:
        """Return the stable first cancellation reason when present."""
        # Active state and reasonless cancellation are distinguished separately.
        return self._reason

    @property
    def subscriber_count(self) -> int:
        """Return the number of callbacks still awaiting cancellation."""
        # The count is test-only evidence that send releases context references.
        return len(self._callbacks)

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Register a callback or notify it immediately after cancellation."""
        if self._is_cancelled:
            # Late subscribers cannot miss an already completed transition.
            callback(self._reason)
            return _noop_unsubscribe

        key = self._next_key
        self._next_key += 1
        self._callbacks[key] = callback
        is_active = True

        def unsubscribe() -> None:
            """Remove this callback exactly once."""
            nonlocal is_active
            if not is_active:
                return
            # Clear the guard first so reentrant cleanup remains idempotent.
            is_active = False
            self._callbacks.pop(key, None)

        return unsubscribe

    def cancel(self, reason: str | None = None) -> None:
        """Apply the first cancellation and notify current subscribers once."""
        if self._is_cancelled:
            return
        self._is_cancelled = True
        self._reason = reason
        callbacks = tuple(self._callbacks.values())
        self._callbacks.clear()

        # Clear shared storage before callbacks so reentrant removers are no-ops.
        for callback in callbacks:
            callback(reason)


def _noop_unsubscribe() -> None:
    """Represent removal after synchronous cancellation delivery."""
    # No state remains for a late subscriber, so cleanup is intentionally empty.
    return None


def _request() -> TransportRequest:
    """Build one complete immutable request for mock dispatch."""
    # The request carries distinct protocol-neutral values but the behavior-only
    # mock deliberately neither serializes nor stores them.
    return TransportRequest(
        "POST",
        UriValue("https://models.example.test/v1/run", True),
        Headers(),
        QueryParameters(),
        TransportBody(Bytes(b'{"input":"hello"}'), MediaType("application", "json")),
    )


def _response() -> TransportResponse:
    """Build one complete successful protocol-neutral response."""
    # A prebuilt value makes response identity observable without native I/O.
    return TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("success")),
            Headers(),
            status_code=200,
        ),
        Bytes(b'{"status":"completed"}'),
    )


def _context(signal: _ControllableSignal | None = None) -> TransportContext:
    """Build complete interaction controls with optional cancellation."""
    # Finite limits satisfy the transport boundary without affecting mock delay.
    return TransportContext(
        "interaction-1",
        ResolvedInteractionResourceLimits(4_096, 1_024, 512),
        cancellation=signal,
    )


def _mock(
    *,
    response: TransportResponse | None = None,
    error: BaseException | None = None,
    delay: Duration = _ZERO_DELAY,
) -> MockTransport:
    """Create one valid MockTransport with deterministic configuration."""
    # None is only a helper convenience; the public constructor always receives
    # a concrete response even when an error overrides it.
    configured_response = _response() if response is None else response
    return MockTransport(
        ComponentDescriptor("Mock transport", "1", "application"),
        configured_response,
        error=error,
        delay=delay,
    )


def test_mock_structurally_implements_transport_and_returns_exact_response() -> None:
    """Return the configured response through the exact asynchronous contract."""
    response = _response()
    mock = _mock(response=response)

    accepted: Transport = mock
    result = asyncio.run(mock.send(_request(), _context()))

    # Static and runtime conformance agree, and identity proves no response copy,
    # normalization, decoding, or assembly occurred.
    assert accepted is mock
    assert isinstance(mock, Transport)
    assert mock.descriptor.name == "Mock transport"
    assert result is response


def test_mock_raises_exact_configured_error_after_delay() -> None:
    """Keep dispatch pending for the delay, then preserve failure identity."""

    async def scenario() -> None:
        """Observe pending state before awaiting the configured failure."""
        failure = OSError("network disconnected")
        mock = _mock(error=failure, delay=Duration(20_000_000))
        task = asyncio.create_task(mock.send(_request(), _context()))
        await asyncio.sleep(0)

        # One event-loop turn is shorter than the configured delay, proving the
        # outcome is not evaluated immediately or by synchronous blocking.
        assert not task.done()
        try:
            await task
        except OSError as error:
            assert error is failure
        else:
            raise AssertionError("Expected configured transport failure.")

    asyncio.run(scenario())


def test_mock_rejects_pre_cancelled_context_before_configured_outcome() -> None:
    """Let existing context cancellation override response and failure."""
    signal = _ControllableSignal()
    signal.cancel("caller_requested")
    failure = RuntimeError("must not win")
    mock = _mock(error=failure, delay=Duration(1_000_000_000))

    try:
        asyncio.run(mock.send(_request(), _context(signal)))
    except asyncio.CancelledError as error:
        # The stable signal reason remains available through standard args and
        # the pre-cancelled call creates no pending subscription.
        assert error.args == ("caller_requested",)
    else:
        raise AssertionError("Expected pre-cancelled transport dispatch.")
    assert signal.subscriber_count == 0


def test_mock_interrupts_delay_and_removes_cancellation_subscription() -> None:
    """Cancel in-flight delay and release the signal callback on every exit."""

    async def scenario() -> None:
        """Trigger cancellation only after send has subscribed."""
        signal = _ControllableSignal()
        mock = _mock(delay=Duration(5_000_000_000))
        task = asyncio.create_task(mock.send(_request(), _context(signal)))

        # Two loop turns allow send to enter its cancellation-aware wait without
        # relying on wall-clock sleeps or private mock state.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert signal.subscriber_count == 1
        signal.cancel("test_cancelled")

        try:
            await task
        except asyncio.CancelledError as error:
            assert error.args == ("test_cancelled",)
        else:
            raise AssertionError("Expected in-flight transport cancellation.")
        assert signal.subscriber_count == 0

    asyncio.run(scenario())


def test_mock_removes_subscription_after_success_and_external_task_cancel() -> None:
    """Avoid retaining context callbacks after either terminal path."""

    async def scenario() -> None:
        """Exercise normal completion and caller-owned task cancellation."""
        successful_signal = _ControllableSignal()
        result = await _mock().send(_request(), _context(successful_signal))
        assert result.body == b'{"status":"completed"}'
        assert successful_signal.subscriber_count == 0

        cancelled_signal = _ControllableSignal()
        task = asyncio.create_task(
            _mock(delay=Duration(5_000_000_000)).send(
                _request(), _context(cancelled_signal)
            )
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert cancelled_signal.subscriber_count == 1
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("Expected caller-owned task cancellation.")
        assert cancelled_signal.subscriber_count == 0

    asyncio.run(scenario())


def test_mock_validates_configuration_and_dynamic_dispatch_boundaries() -> None:
    """Reject malformed fixture setup, negative delay, and invalid inputs."""
    descriptor = ComponentDescriptor("Mock transport", "1", "application")
    response = _response()
    invalid_calls: tuple[tuple[Callable[[], object], type[BaseException], str], ...] = (
        (
            lambda: MockTransport(cast(ComponentDescriptor, object()), response),
            TypeError,
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: MockTransport(descriptor, cast(TransportResponse, object())),
            TypeError,
            "response must be a TransportResponse",
        ),
        (
            lambda: MockTransport(
                descriptor,
                response,
                error=cast(BaseException, "failure"),
            ),
            TypeError,
            "error must be a BaseException or None",
        ),
        (
            lambda: MockTransport(
                descriptor,
                response,
                delay=cast(Duration, object()),
            ),
            TypeError,
            "delay must be a Duration",
        ),
        (
            lambda: MockTransport(descriptor, response, delay=Duration(-1)),
            ValueError,
            "delay must not be negative",
        ),
        (
            lambda: asyncio.run(
                _mock().send(cast(TransportRequest, object()), _context())
            ),
            TypeError,
            "request must be a TransportRequest",
        ),
        (
            lambda: asyncio.run(
                _mock().send(_request(), cast(TransportContext, object()))
            ),
            TypeError,
            "context must be a TransportContext",
        ),
    )

    for action, exception_type, message in invalid_calls:
        try:
            action()
        except exception_type as error:
            # Stable diagnostics identify invalid setup rather than accidentally
            # satisfying a configured transport-failure assertion.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid MockTransport usage to fail.")


def test_mock_matches_transport_surface_without_recording_or_runtime_policy() -> None:
    """Expose exact send behavior without adjacent testing responsibilities."""
    mock = _mock()
    send = MockTransport.send

    # Signature and coroutine semantics remain exactly aligned with Transport.
    assert tuple(inspect.signature(send).parameters) == (
        "self",
        "request",
        "context",
    )
    assert get_type_hints(send) == {
        "request": TransportRequest,
        "context": TransportContext,
        "return": TransportResponse,
    }
    assert inspect.iscoroutinefunction(send)

    # Input recording is the next dedicated wrapper's concern; deadline policy,
    # retry, decoding, reconfiguration, and cancellation ownership remain absent.
    for forbidden_member in (
        "calls",
        "requests",
        "contexts",
        "configure",
        "reset",
        "cancel",
        "now",
        "retry",
        "decode",
        "send_http",
    ):
        assert not hasattr(mock, forbidden_member)
