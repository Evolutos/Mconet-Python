"""Loopback tests for the system HTTP transport."""

import asyncio
import time
from collections.abc import Callable
from typing import cast

from mconet.core.domain import (
    Bytes,
    Duration,
    HeaderField,
    Headers,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    Timestamp,
    UriValue,
)
from mconet.core.spi import TransportBody, TransportContext, TransportRequest
from mconet.testing import (
    ControllableCancellationSignal,
    MockHttpResponseScript,
    MockHttpServer,
)
from mconet.transport.http_system import (
    DefaultSystemHttpTransport,
    HttpProxyOverride,
)


def _request(url: UriValue, *, body: bytes = b"{}") -> TransportRequest:
    """Build one JSON request against a loopback server."""
    return TransportRequest(
        method="POST",
        url=url,
        headers=Headers(()),
        query=QueryParameters((QueryParameter("q", "a b"),)),
        body=TransportBody(Bytes(body), MediaType("application", "json")),
    )


def _context(
    *,
    deadline: Timestamp | None = None,
    cancellation: ControllableCancellationSignal | None = None,
    max_response_body_bytes: int = 1024,
) -> TransportContext:
    """Build one transport context with finite limits."""
    return TransportContext(
        interaction_id="interaction-1",
        resource_limits=ResolvedInteractionResourceLimits(
            max_response_body_bytes,
            1024,
            1024,
        ),
        deadline=deadline,
        cancellation=cancellation,
    )


def _transport(**kwargs: object) -> DefaultSystemHttpTransport:
    """Build a transport that does not read the process proxy environment."""
    environment = kwargs.get("proxy_environment", {})
    return DefaultSystemHttpTransport(
        proxy_environment=cast(dict[str, str], environment),
        proxy_override=cast(HttpProxyOverride | None, kwargs.get("proxy_override")),
        now=cast(Callable[[], Timestamp] | None, kwargs.get("now")),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_system_http_transport_sends_one_unary_request() -> None:
    """Verify status, body, query, and default headers survive one exchange."""
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=b'{"ok":true}',
    )
    transport = _transport()
    with MockHttpServer((script,)) as server:
        response = asyncio.run(transport.send(_request(server.uri), _context()))
        recorded = server.requests

    assert response.response_metadata.status_code == 200
    assert str(response.response_metadata.outcome) == "success"
    assert response.body == b'{"ok":true}'
    assert response.response_metadata.media_type == MediaType("application", "json")
    assert len(recorded) == 1
    assert recorded[0].target == "/?q=a+b"
    assert recorded[0].body == b"{}"
    assert "application/json" in recorded[0].headers.get_all("Accept")
    assert "mconet-sdk" in recorded[0].headers.get_all("User-Agent")


def test_system_http_transport_keeps_a_redirect_without_following_it() -> None:
    """Verify a 3xx response is a service error and does not create a second request."""
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
    assert response.body == b"moved"


def test_system_http_transport_stops_when_the_deadline_has_passed() -> None:
    """Verify an expired deadline fails before a connection is opened."""
    script = MockHttpResponseScript(status_code=200, body=b"late")
    transport = _transport(now=lambda: Timestamp(epoch_seconds=20))
    with MockHttpServer((script,)) as server:
        error = _assert_raises(
            ModelInteractionError,
            lambda: asyncio.run(
                transport.send(
                    _request(server.uri),
                    _context(deadline=Timestamp(epoch_seconds=10)),
                )
            ),
            "deadline expired",
        )
        assert server.requests == ()

    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.code == "deadline_exceeded"
    assert interaction_error.category.id == OpenIdentifier("timeout")


def test_system_http_transport_releases_an_oversized_response() -> None:
    """Verify a body past the limit fails and does not return a prefix."""
    script = MockHttpResponseScript(status_code=200, body=b"abcdef")
    with MockHttpServer((script,)) as server:
        error = _assert_raises(
            ModelInteractionError,
            lambda: asyncio.run(
                _transport().send(
                    _request(server.uri),
                    _context(max_response_body_bytes=4),
                )
            ),
            "exceeds its byte limit",
        )

    assert cast(ModelInteractionError, error).code == "response_body_too_large"


def test_system_http_transport_uses_a_direct_override_instead_of_the_environment() -> (
    None
):
    """Verify an explicit direct connection ignores an unusable proxy variable."""
    script = MockHttpResponseScript(status_code=200, body=b"direct")
    transport = _transport(
        proxy_environment={"http_proxy": "http://127.0.0.1:1"},
        proxy_override=HttpProxyOverride(None),
    )
    with MockHttpServer((script,)) as server:
        response = asyncio.run(transport.send(_request(server.uri), _context()))

    assert response.body == b"direct"


def test_system_http_transport_cancels_an_in_flight_exchange() -> None:
    """Verify caller cancellation aborts a delayed response."""
    script = MockHttpResponseScript(
        status_code=200,
        body=b"slow",
        delay=Duration(2_000_000_000),
    )
    signal = ControllableCancellationSignal()

    async def exchange(server_uri: UriValue) -> None:
        task = asyncio.create_task(
            _transport().send(
                _request(server_uri),
                _context(cancellation=signal),
            )
        )
        await asyncio.sleep(0.05)
        signal.cancel("stop-this-attempt")
        await task

    with MockHttpServer((script,)) as server:
        started = time.monotonic()
        error = _assert_raises(
            asyncio.CancelledError,
            lambda: asyncio.run(exchange(server.uri)),
            "stop-this-attempt",
        )
        # The peer delay is still running. Cancellation must unblock the client
        # before that delay ends.
        assert time.monotonic() - started < 1.0

    assert cast(asyncio.CancelledError, error).args == ("stop-this-attempt",)
