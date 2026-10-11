"""Transport contract cases for the system HTTP client."""

import asyncio

from mconet.core.domain import (
    Bytes,
    Duration,
    Headers,
    MediaType,
    ModelInteractionError,
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
    MockHttpResponseScript,
    MockHttpServer,
    TransportContractSuite,
)
from mconet.transport.http_system import DefaultSystemHttpTransport


def _request(url: UriValue) -> TransportRequest:
    """Build one JSON request for a contract exchange."""
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
    """Build one contract context."""
    return TransportContext(
        interaction_id="contract-1",
        resource_limits=ResolvedInteractionResourceLimits(
            max_response_body_bytes,
            1024,
            1024,
        ),
        deadline=deadline,
        cancellation=cancellation,
    )


def _transport() -> DefaultSystemHttpTransport:
    """Build a transport that does not read the process proxy environment."""
    return DefaultSystemHttpTransport(proxy_environment={})


def test_system_http_transport_contract_success_and_service_error() -> None:
    """Verify the contract suite accepts a 2xx body and a service-error status."""

    async def run(server: MockHttpServer) -> None:
        suite = TransportContractSuite(_transport())
        await suite.assert_send(
            _request(server.uri),
            _context(),
            assertion=lambda response: _assert_status(response, 200, "success", b"ok"),
        )
        await suite.assert_send(
            _request(server.uri),
            _context(),
            assertion=lambda response: _assert_status(
                response, 500, "service_error", b"bad"
            ),
        )

    scripts = (
        MockHttpResponseScript(status_code=200, body=b"ok"),
        MockHttpResponseScript(status_code=500, body=b"bad"),
    )
    with MockHttpServer(scripts) as server:
        asyncio.run(run(server))


def test_system_http_transport_contract_timeout_and_over_limit() -> None:
    """Verify deadline expiry and an oversized body fail through the suite."""
    script = MockHttpResponseScript(status_code=200, body=b"abcdef")
    transport_clock = DefaultSystemHttpTransport(
        proxy_environment={},
        now=lambda: Timestamp(epoch_seconds=10),
    )

    async def run_with_clock(url: UriValue) -> None:
        suite = TransportContractSuite(transport_clock)
        await suite.assert_send_failure(
            _request(url),
            _context(deadline=Timestamp(epoch_seconds=1)),
            assertion=lambda error: _assert_code(error, "deadline_exceeded"),
        )

    with MockHttpServer((script,)) as server:
        asyncio.run(run_with_clock(server.uri))
        asyncio.run(
            TransportContractSuite(_transport()).assert_send_failure(
                _request(server.uri),
                _context(max_response_body_bytes=4),
                assertion=lambda error: _assert_code(error, "response_body_too_large"),
            )
        )


def test_system_http_transport_contract_cancellation() -> None:
    """Verify the contract suite observes in-flight caller cancellation."""
    signal = ControllableCancellationSignal()
    script = MockHttpResponseScript(
        status_code=200,
        body=b"slow",
        delay=Duration(2_000_000_000),
    )

    async def run(url: UriValue) -> None:
        suite = TransportContractSuite(_transport())
        await suite.assert_send_cancellation(
            _request(url),
            _context(cancellation=signal),
            cancel=lambda: signal.cancel("contract-cancel"),
            assertion=lambda error: _assert_cancel(error),
        )

    with MockHttpServer((script,)) as server:
        asyncio.run(run(server.uri))


def _assert_status(
    response: TransportResponse,
    status_code: int,
    outcome: str,
    body: bytes,
) -> None:
    """Check the status, outcome, and body of one contract response."""
    assert response.response_metadata.status_code == status_code
    assert str(response.response_metadata.outcome) == outcome
    assert response.body == body


def _assert_code(error: BaseException, code: str) -> None:
    """Check one contract failure's stable code."""
    assert isinstance(error, ModelInteractionError)
    assert error.code == code


def _assert_cancel(error: asyncio.CancelledError) -> None:
    """Check that cancellation kept the caller reason."""
    assert error.args == ("contract-cancel",)
