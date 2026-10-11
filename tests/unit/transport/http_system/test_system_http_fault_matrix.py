"""Fault matrix for the system HTTP client against the mock server."""

import asyncio
import time
from collections.abc import Awaitable

from mconet.core.domain import (
    Bytes,
    Duration,
    HeaderField,
    Headers,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    Timestamp,
    UriValue,
)
from mconet.core.spi import (
    TransportBody,
    TransportContext,
    TransportRequest,
    TransportResponse,
)
from mconet.testing import (
    ControllableCancellationSignal,
    MockHttpAbort,
    MockHttpResponseScript,
    MockHttpServer,
)
from mconet.transport.http_system import DefaultSystemHttpTransport

_SECRET = b"fault-secret-body"


def _request(url: UriValue) -> TransportRequest:
    """Build one JSON request for a fault exchange."""
    return TransportRequest(
        method="POST",
        url=url,
        headers=Headers(()),
        query=QueryParameters(()),
        body=TransportBody(Bytes(b"{}"), MediaType("application", "json")),
    )


def _context(
    *,
    deadline: Timestamp | None = None,
    cancellation: ControllableCancellationSignal | None = None,
    max_response_body_bytes: int = 1024,
) -> TransportContext:
    """Build one fault-matrix context."""
    return TransportContext(
        interaction_id="fault-1",
        resource_limits=ResolvedInteractionResourceLimits(
            max_response_body_bytes,
            1024,
            1024,
        ),
        deadline=deadline,
        cancellation=cancellation,
    )


def _transport(*, now: Timestamp | None = None) -> DefaultSystemHttpTransport:
    """Build a transport that does not read the process proxy environment."""
    if now is None:
        return DefaultSystemHttpTransport(proxy_environment={})
    return DefaultSystemHttpTransport(proxy_environment={}, now=lambda: now)


async def _expect_error(
    send: Awaitable[TransportResponse],
) -> ModelInteractionError:
    """Await one send and return its model interaction error."""
    try:
        await send
    except ModelInteractionError as error:
        return error
    raise AssertionError("Expected ModelInteractionError to be raised.")


def test_fault_matrix_reports_a_non_success_status() -> None:
    """Verify a non-2xx status stays a service error and keeps its body."""
    script = MockHttpResponseScript(status_code=404, body=b"missing")
    with MockHttpServer((script,)) as server:
        response = asyncio.run(_transport().send(_request(server.uri), _context()))

    assert response.response_metadata.status_code == 404
    assert str(response.response_metadata.outcome) == "service_error"
    assert response.body == b"missing"


def test_fault_matrix_hides_a_truncated_response_body() -> None:
    """Verify a cut body is a connection failure and does not return the prefix."""
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=_SECRET,
        abort=MockHttpAbort("during_body"),
        body_prefix_length=4,
    )
    with MockHttpServer((script,)) as server:
        error = asyncio.run(
            _expect_error(_transport().send(_request(server.uri), _context()))
        )

    assert error.code == "http_connection_failed"
    assert error.phase.id == OpenIdentifier("transport")
    assert _SECRET.decode() not in str(error)
    assert error.cause is None


def test_fault_matrix_maps_a_socket_timeout_separately_from_the_deadline() -> None:
    """Verify a blocked peer becomes a network timeout before the deadline."""
    now = Timestamp(epoch_seconds=1_700_000_000)
    script = MockHttpResponseScript(
        status_code=200,
        body=b"late",
        delay=Duration(2_000_000_000),
    )
    deadline = Timestamp(epoch_seconds=now.epoch_seconds, nanosecond=200_000_000)
    with MockHttpServer((script,)) as server:
        started = time.monotonic()
        error = asyncio.run(
            _expect_error(
                _transport(now=now).send(
                    _request(server.uri),
                    _context(deadline=deadline),
                )
            )
        )
        elapsed = time.monotonic() - started

    assert error.code == "network_timeout"
    assert error.code != "deadline_exceeded"
    assert elapsed < 1.0


def test_fault_matrix_cancels_a_delayed_response() -> None:
    """Verify caller cancellation returns before the scripted delay ends."""
    signal = ControllableCancellationSignal()
    script = MockHttpResponseScript(
        status_code=200,
        body=b"slow",
        delay=Duration(2_000_000_000),
    )

    async def exchange(url: UriValue) -> None:
        task = asyncio.create_task(
            _transport().send(_request(url), _context(cancellation=signal))
        )
        await asyncio.sleep(0.05)
        signal.cancel("fault-cancel")
        await task

    with MockHttpServer((script,)) as server:
        started = time.monotonic()
        try:
            asyncio.run(exchange(server.uri))
        except asyncio.CancelledError as error:
            assert error.args == ("fault-cancel",)
            assert time.monotonic() - started < 1.0
            return
    raise AssertionError("Expected CancelledError to be raised.")


def test_fault_matrix_does_not_follow_a_redirect() -> None:
    """Verify a redirect is one service error and does not open a second request."""
    script = MockHttpResponseScript(
        status_code=302,
        headers=Headers((HeaderField("Location", "https://other.example.test/next"),)),
        body=b"moved",
    )
    with MockHttpServer((script,)) as server:
        response = asyncio.run(_transport().send(_request(server.uri), _context()))
        assert len(server.requests) == 1

    assert response.response_metadata.status_code == 302
    assert str(response.response_metadata.outcome) == "service_error"


def test_fault_matrix_stops_an_oversized_body() -> None:
    """Verify a body past the limit fails without returning the extra bytes."""
    script = MockHttpResponseScript(status_code=200, body=_SECRET)
    with MockHttpServer((script,)) as server:
        error = asyncio.run(
            _expect_error(
                _transport().send(
                    _request(server.uri),
                    _context(max_response_body_bytes=4),
                )
            )
        )

    assert error.code == "response_body_too_large"
    assert _SECRET.decode() not in str(error)
