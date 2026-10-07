"""Input identity, ordering, and transparency tests for RecordingTransport."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import (
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    Timestamp,
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
from mconet.testing import MockTransport, RecordingTransport


def _request(marker: str = "first") -> TransportRequest:
    """Build one distinguishable complete immutable transport request."""
    # Repeated headers and explicit query/body values make every dispatch field
    # independently assertable without depending on native request serialization.
    return TransportRequest(
        "POST",
        UriValue(f"https://models.example.test/v1/{marker}", True),
        Headers(
            (
                HeaderField("X-Trace", f"trace-{marker}"),
                HeaderField("X-Trace", f"trace-{marker}-continued"),
            )
        ),
        QueryParameters((QueryParameter("region", marker),)),
        TransportBody(
            Bytes(f'{{"marker":"{marker}"}}'.encode()),
            MediaType("application", "json"),
        ),
    )


def _context(marker: str = "first") -> TransportContext:
    """Build one distinguishable complete immutable transport context."""
    # Distinct correlation, limit, deadline, and extension facts prove the
    # recorder retains the complete original context instead of rebuilding it.
    return TransportContext(
        f"interaction-{marker}",
        ResolvedInteractionResourceLimits(4_096, 1_024, 512),
        deadline=Timestamp(1_800_000_000, 123_456_789),
        extensions={"test.marker": marker},
    )


def _response(marker: str = "first") -> TransportResponse:
    """Build one protocol-neutral response for delegate composition."""
    # A prebuilt immutable response makes transparent return identity observable.
    return TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("success")),
            Headers((HeaderField("X-Response", marker),)),
            status_code=200,
        ),
        Bytes(f'{{"result":"{marker}"}}'.encode()),
    )


def _delegate(
    *,
    response: TransportResponse | None = None,
    error: BaseException | None = None,
) -> MockTransport:
    """Create one complete deterministic transport for decorator tests."""
    # MockTransport owns outcome behavior while RecordingTransport contributes
    # only input evidence, demonstrating their intended composition boundary.
    configured_response = _response() if response is None else response
    return MockTransport(
        ComponentDescriptor("Delegate transport", "1", "application"),
        configured_response,
        error=error,
    )


def test_recording_transport_structurally_implements_transport() -> None:
    """Expose the delegate descriptor and exact asynchronous send contract."""
    delegate = _delegate()
    recorder = RecordingTransport(delegate)

    accepted: Transport = recorder

    # Static and runtime protocol recognition agree without a wrapper-specific
    # component descriptor, inheritance requirement, or registry entry.
    assert accepted is recorder
    assert isinstance(recorder, Transport)
    assert recorder.descriptor is delegate.descriptor
    assert recorder.descriptor.name == "Delegate transport"


def test_recording_transport_captures_every_request_and_context_field() -> None:
    """Retain exact input identities for complete dispatch assertions."""
    recorder = RecordingTransport(_delegate())
    request = _request()
    context = _context()

    asyncio.run(recorder.send(request, context))

    # The paired call exposes the original values, so tests can assert every
    # protocol-neutral request field and the complete context without copies.
    assert len(recorder.calls) == 1
    recorded_request, recorded_context = recorder.calls[0]
    assert recorded_request is request
    assert recorded_context is context
    assert recorded_request.method == "POST"
    assert recorded_request.url is request.url
    assert recorded_request.url.value == "https://models.example.test/v1/first"
    assert recorded_request.headers is request.headers
    assert recorded_request.headers.get_all("X-Trace") == (
        "trace-first",
        "trace-first-continued",
    )
    assert recorded_request.query is request.query
    assert recorded_request.query.values[0].value == "first"
    assert recorded_request.body is request.body
    assert recorded_request.body.bytes == b'{"marker":"first"}'
    assert recorded_context.interaction_id == "interaction-first"
    assert recorded_context.resource_limits is context.resource_limits
    assert recorded_context.deadline is context.deadline
    assert recorded_context.extensions is context.extensions


def test_recording_transport_preserves_order_and_snapshot_membership() -> None:
    """Keep paired invocation order while earlier tuple views stay time-bounded."""
    recorder = RecordingTransport(_delegate())
    first_request = _request("first")
    first_context = _context("first")
    second_request = _request("second")
    second_context = _context("second")

    asyncio.run(recorder.send(first_request, first_context))
    first_snapshot = recorder.calls
    asyncio.run(recorder.send(second_request, second_context))

    # A new immutable outer tuple is returned each time; nested pair order keeps
    # request/context alignment across repeated transport dispatches.
    assert first_snapshot == ((first_request, first_context),)
    assert recorder.calls == (
        (first_request, first_context),
        (second_request, second_context),
    )
    assert recorder.calls[1][0] is second_request
    assert recorder.calls[1][1] is second_context
    assert not hasattr(recorder.calls, "append")
    assert not hasattr(recorder.calls[0], "append")


def test_recording_transport_returns_exact_delegate_response() -> None:
    """Remain transparent to the successful delegate result."""
    response = _response("configured")
    recorder = RecordingTransport(_delegate(response=response))

    result = asyncio.run(recorder.send(_request(), _context()))

    # Identity proves the decorator does not copy, normalize, decode, or wrap a
    # response after the delegate finishes.
    assert result is response
    assert result.body == b'{"result":"configured"}'


def test_recording_transport_records_before_propagating_delegate_failure() -> None:
    """Expose a failed attempt and preserve the delegate exception identity."""
    failure = OSError("connection reset")
    recorder = RecordingTransport(_delegate(error=failure))
    request = _request()
    context = _context()

    try:
        asyncio.run(recorder.send(request, context))
    except OSError as error:
        # The recorder neither suppresses nor translates the configured failure.
        assert error is failure
    else:
        raise AssertionError("Expected delegate transport failure.")

    assert recorder.calls == ((request, context),)


def test_recording_transport_records_before_external_task_cancellation() -> None:
    """Keep the dispatch visible when the caller cancels an in-flight delegate."""

    async def scenario() -> None:
        """Cancel a blocking structural delegate after wrapper entry."""

        class _BlockingTransport:
            """Wait indefinitely until its send task is externally cancelled."""

            descriptor = ComponentDescriptor("Blocking transport", "1", "application")
            """Static metadata satisfying RuntimeComponent."""

            async def send(
                self,
                request: TransportRequest,
                context: TransportContext,
            ) -> TransportResponse:
                """Accept exact inputs and wait without producing a response."""
                # Inputs are deliberately unused after crossing the contract;
                # caller cancellation is the only terminal path for this fixture.
                del request, context
                await asyncio.Event().wait()
                raise AssertionError("Unreachable blocking transport completion.")

        recorder = RecordingTransport(_BlockingTransport())
        request = _request()
        context = _context()
        task = asyncio.create_task(recorder.send(request, context))
        await asyncio.sleep(0)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("Expected caller-owned task cancellation.")
        assert recorder.calls == ((request, context),)

    asyncio.run(scenario())


def test_recording_transport_validates_delegate_and_dynamic_inputs() -> None:
    """Reject incomplete delegates and invalid dispatch values before recording."""
    recorder = RecordingTransport(_delegate())

    class _InvalidDescriptorTransport:
        """Expose send behavior with invalid component metadata."""

        descriptor = object()
        """Invalid metadata retained to exercise the dynamic boundary."""

        async def send(
            self,
            request: TransportRequest,
            context: TransportContext,
        ) -> TransportResponse:
            """Return a valid response so only metadata is malformed."""
            # Inputs cross the expected signature but do not affect this fixture.
            del request, context
            return _response()

    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: RecordingTransport(cast(Transport, object())),
            "transport must implement Transport",
        ),
        (
            lambda: RecordingTransport(cast(Transport, _InvalidDescriptorTransport())),
            "transport descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: asyncio.run(
                recorder.send(cast(TransportRequest, object()), _context())
            ),
            "request must be a TransportRequest",
        ),
        (
            lambda: asyncio.run(
                recorder.send(_request(), cast(TransportContext, object()))
            ),
            "context must be a TransportContext",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Stable diagnostics distinguish wrapper misuse from a delegate's
            # intentional transport failure used by a scenario test.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid RecordingTransport usage.")

    # Invalid calls fail before append, leaving no misleading dispatch evidence.
    assert recorder.calls == ()


def test_recording_transport_has_exact_minimal_surface() -> None:
    """Expose only transparent send plus the required paired call history."""
    recorder = RecordingTransport(_delegate())
    send = RecordingTransport.send

    # Signature and coroutine behavior remain exactly aligned with Transport.
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

    # Response configuration belongs to MockTransport; cross-component ordering,
    # request mutation, network behavior, and history reset remain separate.
    for forbidden_member in (
        "response",
        "error",
        "delay",
        "configure",
        "reset",
        "replace_headers",
        "send_http",
        "component_calls",
    ):
        assert not hasattr(recorder, forbidden_member)
