"""Request, response, failure, and cancellation tests for TransportContractSuite."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import cast, get_type_hints

from mconet.core.domain import (
    Bytes,
    Duration,
    HeaderField,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameter,
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
from mconet.testing import (
    ComponentCallRecorder,
    ControllableCancellationSignal,
    MockTransport,
    RecordingTransport,
    TransportContractSuite,
)

_ZERO_DELAY = Duration(0)


def _request() -> TransportRequest:
    """Build one complete distinguishable immutable dispatch request."""
    return TransportRequest(
        "POST",
        UriValue("https://models.example.test/v1/run", True),
        Headers((HeaderField("X-Trace", "trace-1"),)),
        QueryParameters((QueryParameter("region", "test"),)),
        TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def _context(
    signal: ControllableCancellationSignal | None = None,
) -> TransportContext:
    """Build complete interaction controls with optional cancellation."""
    return TransportContext(
        "interaction-1",
        ResolvedInteractionResourceLimits(4_096, 1_024, 512),
        cancellation=signal,
        extensions={"test.case": "transport-contract"},
    )


def _response() -> TransportResponse:
    """Build one complete protocol-neutral response for contract cases."""
    return TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("success")),
            Headers((HeaderField("X-Request-Id", "request-1"),)),
            status_code=200,
            media_type=MediaType("application", "json"),
            request_id="request-1",
        ),
        Bytes(b'{"status":"completed"}'),
    )


def _mock(
    *,
    response: TransportResponse | None = None,
    error: BaseException | None = None,
    delay: Duration = _ZERO_DELAY,
) -> MockTransport:
    """Build one deterministic mock with a selected outcome."""
    configured_response = _response() if response is None else response
    return MockTransport(
        ComponentDescriptor("Contract transport", "1", "application"),
        configured_response,
        error=error,
        delay=delay,
    )


class _RecordingStructuralTransport:
    """Custom structural transport retaining exact invocation evidence."""

    __slots__ = ("_calls", "_descriptor", "_recorder", "_response")

    def __init__(
        self,
        response: TransportResponse,
        recorder: ComponentCallRecorder,
    ) -> None:
        """Retain one exact response and external order recorder."""
        self._descriptor = ComponentDescriptor(
            "Structural transport", "1", "application"
        )
        self._response = response
        self._recorder = recorder
        self._calls: list[tuple[TransportRequest, TransportContext]] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable component metadata."""
        return self._descriptor

    @property
    def calls(self) -> tuple[tuple[TransportRequest, TransportContext], ...]:
        """Return an immutable snapshot of exact dispatch inputs."""
        return tuple(self._calls)

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record exact inputs and return the configured exact response."""
        self._recorder.record("send")
        self._calls.append((request, context))
        await asyncio.sleep(0)
        return self._response


class _InvalidResponseTransport:
    """Claim the Transport signature while returning an invalid value."""

    descriptor = ComponentDescriptor("Invalid transport", "1", "application")

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Discard dispatch inputs and expose malformed implementation output."""
        del request, context
        return cast(TransportResponse, object())


class _InvalidDescriptorTransport:
    """Expose asynchronous send with invalid component metadata."""

    descriptor = cast(ComponentDescriptor, object())

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Provide the method shape required for descriptor validation."""
        del request, context
        return _response()


class _SynchronousTransport:
    """Expose an invalid synchronous look-alike Transport operation."""

    descriptor = ComponentDescriptor("Sync transport", "1", "application")

    def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Return immediately instead of crossing the asynchronous boundary."""
        del request, context
        return _response()


def test_suite_validates_request_response_and_recorded_input_contract() -> None:
    """Preserve complete dispatch identities and exact response facts."""

    async def scenario() -> None:
        """Run one successful case through the existing recording decorator."""
        request = _request()
        context = _context()
        response = _response()
        transport = RecordingTransport(_mock(response=response))
        observed: list[TransportResponse] = []

        def assert_response(actual: TransportResponse) -> None:
            """Verify exact response identity and protocol-neutral facts."""
            assert actual is response
            assert actual.response_metadata.status_code == 200
            assert actual.response_metadata.request_id == "request-1"
            assert actual.body == b'{"status":"completed"}'
            observed.append(actual)

        await TransportContractSuite(transport).assert_send(
            request,
            context,
            assertion=assert_response,
        )

        assert observed == [response]
        assert transport.calls == ((request, context),)
        assert transport.calls[0][0] is request
        assert transport.calls[0][1] is context
        assert request.headers.get_all("X-Trace") == ("trace-1",)
        assert request.query.values[0].value == "test"

    asyncio.run(scenario())


def test_suite_accepts_structural_transport_and_dispatches_once() -> None:
    """Require no SDK inheritance while retaining every object identity."""

    async def scenario() -> None:
        """Exercise one ordinary custom class through the public suite."""
        request = _request()
        context = _context()
        response = _response()
        recorder = ComponentCallRecorder()
        transport = _RecordingStructuralTransport(response, recorder)

        def assert_identity(actual: TransportResponse) -> None:
            """Require the exact custom transport response."""
            assert actual is response

        await TransportContractSuite(transport).assert_send(
            request,
            context,
            assertion=assert_identity,
        )

        assert recorder.calls == ("send",)
        assert transport.calls == ((request, context),)

    asyncio.run(scenario())


def test_success_assertion_rejects_invalid_runtime_response() -> None:
    """Require a nominal response before invoking the caller callback."""

    async def scenario() -> None:
        """Dispatch through a malformed dynamic implementation."""
        callback_calls: list[TransportResponse] = []

        def record_unexpected_response(response: TransportResponse) -> None:
            """Record a callback call that invalid output must prevent."""
            callback_calls.append(response)

        try:
            await TransportContractSuite(_InvalidResponseTransport()).assert_send(
                _request(),
                _context(),
                assertion=record_unexpected_response,
            )
        except AssertionError as error:
            assert str(error) == "transport must return a TransportResponse."
        else:
            raise AssertionError("Expected malformed transport output to fail.")
        assert callback_calls == []

    asyncio.run(scenario())


def test_suite_validates_exact_non_cancellation_failure() -> None:
    """Keep failed input evidence and expose the exact transport error."""

    async def scenario() -> None:
        """Run one deterministic failure through the recording decorator."""
        failure = OSError("connection reset")
        request = _request()
        context = _context()
        transport = RecordingTransport(_mock(error=failure))
        observed: list[BaseException] = []

        def assert_failure(actual: BaseException) -> None:
            """Require the exact configured transport failure."""
            assert actual is failure
            observed.append(actual)

        await TransportContractSuite(transport).assert_send_failure(
            request,
            context,
            assertion=assert_failure,
        )

        assert observed == [failure]
        assert transport.calls == ((request, context),)

    asyncio.run(scenario())


def test_failure_assertion_rejects_success_and_propagates_cancellation() -> None:
    """Keep normal completion and cancellation outside the error callback."""

    async def scenario() -> None:
        """Exercise the two outcomes that are not transport failures."""
        recorder = ComponentCallRecorder()
        transport = _RecordingStructuralTransport(_response(), recorder)
        callback_calls: list[BaseException] = []

        def record_unexpected_failure(error: BaseException) -> None:
            """Record a failure callback invocation that must not occur."""
            callback_calls.append(error)

        try:
            await TransportContractSuite(transport).assert_send_failure(
                _request(),
                _context(),
                assertion=record_unexpected_failure,
            )
        except AssertionError as error:
            assert str(error) == "transport was expected to fail."
        else:
            raise AssertionError("Expected successful dispatch to fail the case.")

        signal = ControllableCancellationSignal()
        signal.cancel("already-cancelled")
        try:
            await TransportContractSuite(_mock()).assert_send_failure(
                _request(),
                _context(signal),
                assertion=record_unexpected_failure,
            )
        except asyncio.CancelledError as error:
            assert error.args == ("already-cancelled",)
        else:
            raise AssertionError("Expected cancellation to propagate separately.")

        assert recorder.calls == ("send",)
        assert callback_calls == []

    asyncio.run(scenario())


def test_suite_triggers_and_validates_in_flight_context_cancellation() -> None:
    """Observe signal cancellation, exact inputs, reason, and task cleanup."""

    async def scenario() -> None:
        """Cancel a delayed mock only after its dispatch task begins."""
        signal = ControllableCancellationSignal()
        request = _request()
        context = _context(signal)
        transport = RecordingTransport(_mock(delay=Duration(5_000_000_000)))
        observed: list[asyncio.CancelledError] = []

        def cancel() -> None:
            """Apply one stable reason to the context signal."""
            signal.cancel("contract-cancelled")

        def assert_cancellation(error: asyncio.CancelledError) -> None:
            """Verify normalized cancellation type and preserved reason."""
            assert error.args == ("contract-cancelled",)
            observed.append(error)

        await TransportContractSuite(transport).assert_send_cancellation(
            request,
            context,
            cancel=cancel,
            assertion=assert_cancellation,
        )

        assert signal.is_cancelled
        assert signal.reason == "contract-cancelled"
        assert len(observed) == 1
        assert transport.calls == ((request, context),)

    asyncio.run(scenario())


def test_cancellation_case_rejects_invalid_setup_and_settles_dispatch() -> None:
    """Fail invalid signal cases without leaking a pending send task."""

    async def scenario() -> None:
        """Exercise missing, pre-cancelled, and ineffective signal controls."""
        suite = TransportContractSuite(_mock(delay=Duration(5_000_000_000)))

        def ignore_cancellation(error: asyncio.CancelledError) -> None:
            """Provide a valid callback that invalid setup must not invoke."""
            del error

        def no_cancel() -> None:
            """Leave cancellation active to exercise setup validation."""
            return None

        try:
            await suite.assert_send_cancellation(
                _request(),
                _context(),
                cancel=no_cancel,
                assertion=ignore_cancellation,
            )
        except ValueError as error:
            assert str(error) == "context cancellation must be present."
        else:
            raise AssertionError("Expected a missing cancellation signal to fail.")

        pre_cancelled = ControllableCancellationSignal()
        pre_cancelled.cancel("before-dispatch")
        try:
            await suite.assert_send_cancellation(
                _request(),
                _context(pre_cancelled),
                cancel=no_cancel,
                assertion=ignore_cancellation,
            )
        except ValueError as error:
            assert str(error) == (
                "context cancellation must be active before dispatch."
            )
        else:
            raise AssertionError("Expected pre-cancelled setup to fail.")

        active = ControllableCancellationSignal()
        try:
            await suite.assert_send_cancellation(
                _request(),
                _context(active),
                cancel=no_cancel,
                assertion=ignore_cancellation,
            )
        except AssertionError as error:
            assert str(error) == "cancel must transition the context signal."
        else:
            raise AssertionError("Expected an ineffective cancel action to fail.")

        # The private cleanup path has consumed every internally created task;
        # only this currently running scenario remains in the loop.
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_suite_preserves_transport_trigger_and_callback_failures() -> None:
    """Propagate each independently owned failure by exact identity."""

    async def scenario() -> None:
        """Exercise successful, failed, and cancellation callback boundaries."""
        response_callback_failure = AssertionError("response mismatch")
        failure_callback_failure = AssertionError("failure mismatch")
        cancellation_callback_failure = AssertionError("cancellation mismatch")
        transport_failure = OSError("transport failure")

        def fail_response(response: TransportResponse) -> None:
            """Raise the exact response assertion failure."""
            del response
            raise response_callback_failure

        def fail_transport_error(error: BaseException) -> None:
            """Confirm the transport error, then raise callback failure."""
            assert error is transport_failure
            raise failure_callback_failure

        await _assert_awaitable_raises_identity(
            TransportContractSuite(_mock()).assert_send(
                _request(), _context(), assertion=fail_response
            ),
            response_callback_failure,
        )
        await _assert_awaitable_raises_identity(
            TransportContractSuite(_mock(error=transport_failure)).assert_send_failure(
                _request(), _context(), assertion=fail_transport_error
            ),
            failure_callback_failure,
        )

        signal = ControllableCancellationSignal()

        def cancel() -> None:
            """Transition the context signal for callback failure testing."""
            signal.cancel("callback-case")

        def fail_cancellation(error: asyncio.CancelledError) -> None:
            """Confirm cancellation, then raise the exact callback failure."""
            assert error.args == ("callback-case",)
            raise cancellation_callback_failure

        await _assert_awaitable_raises_identity(
            TransportContractSuite(
                _mock(delay=Duration(5_000_000_000))
            ).assert_send_cancellation(
                _request(),
                _context(signal),
                cancel=cancel,
                assertion=fail_cancellation,
            ),
            cancellation_callback_failure,
        )

        trigger_failure = RuntimeError("cancel trigger failed")
        second_signal = ControllableCancellationSignal()

        def fail_trigger() -> None:
            """Raise before transitioning the signal to exercise cleanup."""
            raise trigger_failure

        def ignore_trigger_cancellation(error: asyncio.CancelledError) -> None:
            """Provide a callback that a failing trigger must not invoke."""
            del error

        await _assert_awaitable_raises_identity(
            TransportContractSuite(
                _mock(delay=Duration(5_000_000_000))
            ).assert_send_cancellation(
                _request(),
                _context(second_signal),
                cancel=fail_trigger,
                assertion=ignore_trigger_cancellation,
            ),
            trigger_failure,
        )
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_cancellation_assertion_preserves_external_task_cancellation() -> None:
    """Never mistake caller-owned task cancellation for signal observation."""

    async def scenario() -> None:
        """Cancel the suite while a transport deliberately ignores its signal."""

        class _IgnoringCancellationTransport:
            """Block until task cancellation without observing context state."""

            descriptor = ComponentDescriptor(
                "Ignoring cancellation transport", "1", "application"
            )

            async def send(
                self,
                request: TransportRequest,
                context: TransportContext,
            ) -> TransportResponse:
                """Accept exact inputs and wait for caller-owned cancellation."""
                del request, context
                await asyncio.Event().wait()
                raise AssertionError("Unreachable transport completion.")

        signal = ControllableCancellationSignal()
        trigger_completed = asyncio.Event()
        callback_calls: list[asyncio.CancelledError] = []

        def cancel_signal() -> None:
            """Transition the signal and expose when the trigger has run."""
            signal.cancel("ignored-by-transport")
            trigger_completed.set()

        def record_unexpected_cancellation(error: asyncio.CancelledError) -> None:
            """Record a false contract success that must never occur."""
            callback_calls.append(error)

        contract_task = asyncio.create_task(
            TransportContractSuite(
                _IgnoringCancellationTransport()
            ).assert_send_cancellation(
                _request(),
                _context(signal),
                cancel=cancel_signal,
                assertion=record_unexpected_cancellation,
            )
        )
        await trigger_completed.wait()
        contract_task.cancel()

        try:
            await contract_task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("Expected caller-owned task cancellation.")

        assert callback_calls == []
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


async def _assert_awaitable_raises_identity(
    awaitable: Awaitable[object],
    expected: BaseException,
) -> None:
    """Await one typed contract operation and require exact failure identity."""
    try:
        await awaitable
    except BaseException as error:
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_suite_validates_transport_and_callbacks_before_dispatch() -> None:
    """Reject malformed setup and callbacks at their exact boundaries."""
    invalid_transports = (
        cast(Transport, object()),
        cast(Transport, _InvalidDescriptorTransport()),
        cast(Transport, _SynchronousTransport()),
    )
    expected_messages = (
        "transport must implement Transport.",
        "transport descriptor must be a ComponentDescriptor.",
        "transport send operation must be asynchronous.",
    )
    for transport, message in zip(invalid_transports, expected_messages, strict=True):
        try:
            TransportContractSuite(transport)
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid transport setup to fail.")

    async def scenario() -> None:
        """Reject invalid callbacks before a structural transport is called."""
        recorder = ComponentCallRecorder()
        suite = TransportContractSuite(
            _RecordingStructuralTransport(_response(), recorder)
        )

        async def async_response(response: TransportResponse) -> None:
            """Provide an invalid async response callback."""
            del response

        invalid_assertions = (
            cast(Callable[[TransportResponse], None], object()),
            cast(Callable[[TransportResponse], None], async_response),
        )
        for assertion in invalid_assertions:
            try:
                await suite.assert_send(_request(), _context(), assertion=assertion)
            except TypeError:
                pass
            else:
                raise AssertionError("Expected invalid assertion callback to fail.")

        signal = ControllableCancellationSignal()

        async def async_cancel() -> None:
            """Provide an invalid async cancellation trigger."""
            signal.cancel()

        def ignore_cancellation(error: asyncio.CancelledError) -> None:
            """Provide a valid assertion while validating the trigger."""
            del error

        try:
            await suite.assert_send_cancellation(
                _request(),
                _context(signal),
                cancel=cast(Callable[[], None], async_cancel),
                assertion=ignore_cancellation,
            )
        except TypeError as error:
            assert str(error) == "cancel must be synchronous."
        else:
            raise AssertionError("Expected async cancellation trigger to fail.")

        assert recorder.calls == ()

    asyncio.run(scenario())


def test_suite_exposes_only_atomic_transport_contract_operations() -> None:
    """Keep exact async signatures and exclude adjacent Runtime behavior."""
    send = TransportContractSuite.assert_send
    failure = TransportContractSuite.assert_send_failure
    cancellation = TransportContractSuite.assert_send_cancellation

    assert tuple(inspect.signature(send).parameters) == (
        "self",
        "request",
        "context",
        "assertion",
    )
    assert tuple(inspect.signature(failure).parameters) == (
        "self",
        "request",
        "context",
        "assertion",
    )
    assert tuple(inspect.signature(cancellation).parameters) == (
        "self",
        "request",
        "context",
        "cancel",
        "assertion",
    )
    assert get_type_hints(send) == {
        "request": TransportRequest,
        "context": TransportContext,
        "assertion": Callable[[TransportResponse], None],
        "return": type(None),
    }
    assert get_type_hints(failure) == {
        "request": TransportRequest,
        "context": TransportContext,
        "assertion": Callable[[BaseException], None],
        "return": type(None),
    }
    assert get_type_hints(cancellation) == {
        "request": TransportRequest,
        "context": TransportContext,
        "cancel": Callable[[], None],
        "assertion": Callable[[asyncio.CancelledError], None],
        "return": type(None),
    }
    assert inspect.iscoroutinefunction(send)
    assert inspect.iscoroutinefunction(failure)
    assert inspect.iscoroutinefunction(cancellation)

    suite = TransportContractSuite(_mock())
    for forbidden_member in (
        "load_fixture",
        "mutate_request",
        "serialize_request",
        "decode_response",
        "retry",
        "calculate_deadline",
        "log",
        "reset",
        "run",
    ):
        assert not hasattr(suite, forbidden_member)
