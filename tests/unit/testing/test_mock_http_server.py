"""Script, delay, and connection-cut tests for MockHttpServer."""

from __future__ import annotations

import http.client
import inspect
import io
import socket
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
from typing import cast

from mconet.core.domain import Bytes, Duration, HeaderField, Headers, UriValue
from mconet.testing import (
    MockHttpAbort,
    MockHttpRequest,
    MockHttpResponseScript,
    MockHttpServer,
)

_DELAY = Duration(100_000_000)
_EMPTY_HEADERS = Headers()
_ZERO_DELAY = Duration(0)
_SECRET = "mconet-test-api-key-not-secret"


def _script(
    status_code: int = 200,
    *,
    headers: Headers | None = None,
    body: bytes = b'{"ok":true}',
    delay: Duration = _ZERO_DELAY,
    abort: MockHttpAbort | None = None,
    body_prefix_length: int | None = None,
) -> MockHttpResponseScript:
    """Build one response script with an explicit empty header default."""
    # None selects the domain empty collection at the fixture edge so each test
    # states only the fields that distinguish its scenario.
    return MockHttpResponseScript(
        status_code,
        _EMPTY_HEADERS if headers is None else headers,
        body,
        delay,
        abort,
        body_prefix_length,
    )


def _headers(*fields: tuple[str, str]) -> Headers:
    """Build an ordered header collection from exact name/value pairs."""
    return Headers(tuple(HeaderField(name, value) for name, value in fields))


def _read(
    server: MockHttpServer,
    *,
    method: str = "POST",
    target: str = "/v1/chat/completions",
    body: bytes | None = b"{}",
    headers: Mapping[str, str] | None = None,
    timeout: float = 2,
) -> tuple[int, tuple[tuple[str, str], ...], bytes]:
    """Perform one HTTP exchange and return status, headers, and body."""
    connection = http.client.HTTPConnection(server.host, server.port, timeout=timeout)
    try:
        connection.request(
            method,
            target,
            body=body,
            headers={} if headers is None else dict(headers),
        )
        response = connection.getresponse()
        # Capture fields before the body read so a later incomplete read still
        # leaves the scripted header block observable.
        fields = tuple((name, value) for name, value in response.getheaders())
        payload = response.read()
        return response.status, fields, payload
    finally:
        connection.close()


def _recv_until_closed(probe: socket.socket) -> bytes:
    """Read one response until the server closes the connection."""
    chunks: list[bytes] = []
    # The server closes after one exchange, so an empty read is the end of the
    # response rather than a stall. The socket timeout bounds a missed close.
    while True:
        chunk = probe.recv(1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _expect(
    action: Callable[[], object],
    error_type: type[BaseException],
    text: str | None = None,
) -> BaseException:
    """Return one expected failure without echoing its text into a new error."""
    try:
        action()
    except error_type as error:
        # Match a stable substring when the contract identifies the branch.
        # Construction failures do not carry request bodies or credentials.
        if text is not None and text not in str(error):
            raise AssertionError(
                "Failure text did not match the expected contract."
            ) from error
        return error
    raise AssertionError("Expected the operation to fail.")


def _header_values(fields: tuple[tuple[str, str], ...], name: str) -> tuple[str, ...]:
    """Return header values whose names match without case sensitivity."""
    folded = name.casefold()
    return tuple(
        value for field_name, value in fields if field_name.casefold() == folded
    )


def test_server_exports_script_and_request_contracts() -> None:
    """Expose the loopback server without pretending it is an in-process transport."""
    constructor = inspect.signature(MockHttpServer)
    parameters = tuple(constructor.parameters)

    # One ordered script is the whole configuration surface. Delay, status,
    # headers, body, and the cut point live on each script entry.
    assert parameters == ("scripts",)
    recorded = MockHttpRequest(
        "POST",
        "/v1/chat/completions",
        "HTTP/1.1",
        _EMPTY_HEADERS,
        Bytes(b"{}"),
    )
    assert recorded.body == b"{}"
    assert MockHttpAbort("before_response").point == "before_response"


def test_script_rejects_invalid_status_delay_headers_and_abort() -> None:
    """Fail closed before a socket exists when the script cannot be emitted."""
    _expect(lambda: MockHttpResponseScript(cast(int, True)), TypeError, "status_code")
    _expect(lambda: MockHttpResponseScript(99), ValueError, "range")
    _expect(
        lambda: MockHttpResponseScript(200, delay=Duration(-1)),
        ValueError,
        "delay",
    )
    _expect(
        lambda: _script(headers=_headers(("X-Test", "bad\r\nX-Injected: 1"))),
        ValueError,
        "header value",
    )
    _expect(lambda: MockHttpAbort("reset"), ValueError, "abort point")
    _expect(
        lambda: _script(abort=MockHttpAbort("during_body")),
        ValueError,
        "body_prefix_length",
    )
    _expect(
        lambda: _script(body=b"", abort=MockHttpAbort("after_headers")),
        ValueError,
        "after_headers",
    )
    _expect(
        lambda: _script(
            body=b"ab",
            abort=MockHttpAbort("during_body"),
            body_prefix_length=2,
        ),
        ValueError,
        "withhold",
    )
    _expect(
        lambda: _script(headers=_headers(("Bad Name", "x"))),
        ValueError,
        "header name",
    )


def test_server_rejects_an_empty_or_mutable_script_source() -> None:
    """Snapshot a non-empty script so later caller mutation cannot add exchanges."""
    _expect(lambda: MockHttpServer(()), ValueError, "at least one")
    _expect(
        lambda: MockHttpServer(
            cast(tuple[MockHttpResponseScript, ...], "not-a-script")
        ),
        TypeError,
        "ordered sequence",
    )

    scripts = [_script(body=b"one")]
    server = MockHttpServer(scripts)
    scripts.append(_script(body=b"two"))

    try:
        with server:
            status, _, payload = _read(server)
            assert status == 200
            assert payload == b"one"
            _expect(lambda: _read(server), OSError)
    except AssertionError as error:
        if "exhausted" not in str(error):
            raise
    else:
        raise AssertionError("Expected exhaustion to fail close.")


def test_running_server_exposes_loopback_uri_and_refuses_restart() -> None:
    """Bind only loopback for the lifetime of one context manager entry."""
    server = MockHttpServer((_script(),))
    _expect(lambda: server.port, RuntimeError, "not running")

    with server:
        assert server.host == "127.0.0.1"
        assert server.port != 0
        assert server.uri == UriValue(f"http://127.0.0.1:{server.port}/", True)
        _expect(server.__enter__, RuntimeError, "started once")
        port = server.port

    _expect(
        lambda: socket.create_connection(("127.0.0.1", port), timeout=1),
        OSError,
    )


def test_scripted_status_headers_and_body_round_trip() -> None:
    """Return the scripted status, ordered headers, and opaque body bytes."""
    body = '{"text":"café 😀"}'.encode()
    script = _script(
        503,
        headers=_headers(
            ("Content-Type", "application/json; charset=utf-8"),
            ("X-Trace", "one"),
            ("X-Trace", "two"),
            ("Location", "https://models.example.test/next"),
        ),
        body=body,
    )

    with MockHttpServer((script,)) as server:
        status, fields, payload = _read(
            server,
            target="/v1/chat/completions?n=1",
            body=b'{"input":"hello"}',
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_SECRET}",
                "X-Request": "alpha",
            },
        )
        recorded = server.requests

    assert status == 503
    assert payload == body
    assert _header_values(fields, "Content-Type") == (
        "application/json; charset=utf-8",
    )
    assert _header_values(fields, "X-Trace") == ("one", "two")
    assert _header_values(fields, "Location") == ("https://models.example.test/next",)
    assert _header_values(fields, "Content-Length") == (str(len(body)),)
    assert _header_values(fields, "Server") == ()
    assert _header_values(fields, "Date") == ()

    assert len(recorded) == 1
    assert recorded[0].method == "POST"
    assert recorded[0].target == "/v1/chat/completions?n=1"
    assert recorded[0].http_version == "HTTP/1.1"
    assert recorded[0].body == b'{"input":"hello"}'
    assert recorded[0].headers.get_all("X-Request") == ("alpha",)
    assert recorded[0].headers.get_all("Authorization") == (f"Bearer {_SECRET}",)


def test_scripted_content_length_is_not_replaced() -> None:
    """Preserve an explicit content length instead of appending a second one."""
    script = _script(
        200,
        headers=_headers(("Content-Length", "3"), ("X-Kind", "fixed")),
        body=b"abc",
    )

    with MockHttpServer((script,)) as server:
        _, fields, payload = _read(server)

    assert payload == b"abc"
    assert _header_values(fields, "Content-Length") == ("3",)
    assert _header_values(fields, "X-Kind") == ("fixed",)


def test_ordered_scripts_follow_request_order() -> None:
    """Consume one distinct exchange per connection, in reservation order."""
    scripts = (
        _script(201, body=b"first"),
        _script(202, body=b"second"),
    )

    with MockHttpServer(scripts) as server:
        first = _read(server, method="POST", body=b"a")
        second = _read(server, method="GET", target="/health", body=None)

    assert first[0] == 201
    assert first[2] == b"first"
    assert second[0] == 202
    assert second[2] == b"second"
    assert tuple(request.method for request in server.requests) == ("POST", "GET")
    assert server.requests[1].target == "/health"
    assert server.requests[1].body == b""


def test_delay_elapses_before_the_response_returns() -> None:
    """Hold the response until the scripted monotonic delay has elapsed."""
    with MockHttpServer((_script(delay=_DELAY, body=b"late"),)) as server:
        started = time.monotonic()
        _, _, payload = _read(server, timeout=2)
        elapsed = time.monotonic() - started

    assert payload == b"late"
    assert elapsed >= _DELAY.total_nanoseconds / 1_000_000_000


def test_before_response_abort_records_the_request_and_sends_no_status() -> None:
    """Close after reading the request and before the status line."""
    with MockHttpServer(
        (_script(body=b"hidden", abort=MockHttpAbort("before_response")),)
    ) as server:
        connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
        try:
            connection.request("POST", "/v1/chat/completions", body=b"{}")
            _expect(connection.getresponse, http.client.HTTPException)
        finally:
            connection.close()
        recorded = server.requests

    assert recorded[0].target == "/v1/chat/completions"
    assert recorded[0].body == b"{}"


def test_after_headers_abort_returns_headers_and_no_body() -> None:
    """Write the status and headers, then close before the promised body."""
    script = _script(
        200,
        headers=_headers(("X-Cut", "headers")),
        body=b"abcdef",
        abort=MockHttpAbort("after_headers"),
    )

    with MockHttpServer((script,)) as server:
        connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
        try:
            connection.request("POST", "/cut", body=b"q")
            response = connection.getresponse()
            assert response.status == 200
            fields = tuple(response.getheaders())
            assert _header_values(fields, "X-Cut") == ("headers",)
            assert _header_values(fields, "Content-Length") == ("6",)
            incomplete = _expect(response.read, http.client.IncompleteRead)
        finally:
            connection.close()

    assert isinstance(incomplete, http.client.IncompleteRead)
    assert incomplete.partial == b""


def test_during_body_abort_returns_only_the_scripted_prefix() -> None:
    """Write a strict body prefix and then close the connection."""
    script = _script(
        200,
        body=b"abcdefgh",
        abort=MockHttpAbort("during_body"),
        body_prefix_length=3,
    )

    with MockHttpServer((script,)) as server:
        connection = http.client.HTTPConnection(server.host, server.port, timeout=2)
        try:
            connection.request("POST", "/cut", body=b"q")
            response = connection.getresponse()
            assert _header_values(tuple(response.getheaders()), "Content-Length") == (
                "8",
            )
            incomplete = _expect(response.read, http.client.IncompleteRead)
        finally:
            connection.close()

    assert isinstance(incomplete, http.client.IncompleteRead)
    assert incomplete.partial == b"abc"
    assert server.requests[0].body == b"q"


def test_malformed_request_does_not_consume_the_script() -> None:
    """Ignore a request that is not a single bounded byte body."""
    with MockHttpServer((_script(body=b"kept"),)) as server:
        probe = socket.create_connection((server.host, server.port), timeout=2)
        try:
            probe.sendall(
                b"POST /bad HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Length: 1\r\n"
                b"Content-Length: 1\r\n"
                b"\r\n"
            )
            probe.shutdown(socket.SHUT_WR)
            assert probe.recv(64) == b""
        finally:
            probe.close()

        status, _, payload = _read(server)

    assert status == 200
    assert payload == b"kept"
    assert len(server.requests) == 1
    assert server.requests[0].target == "/v1/chat/completions"


def test_oversized_content_length_does_not_consume_the_script() -> None:
    """Reject a declared body above the local cap before reading it."""
    with MockHttpServer((_script(body=b"kept"),)) as server:
        probe = socket.create_connection((server.host, server.port), timeout=2)
        try:
            probe.sendall(
                b"POST /huge HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Length: 99999999\r\n"
                b"\r\n"
            )
            probe.shutdown(socket.SHUT_WR)
            assert probe.recv(64) == b""
        finally:
            probe.close()
        _, _, payload = _read(server)

    assert payload == b"kept"
    assert server.requests[0].target == "/v1/chat/completions"


def test_concurrent_requests_consume_each_script_once() -> None:
    """Give overlapping connections distinct reserved exchanges."""
    scripts = (_script(body=b"left"), _script(body=b"right"))
    received: list[bytes] = []
    barrier = threading.Barrier(2)

    def exchange(server: MockHttpServer) -> None:
        """Wait until both clients are ready, then collect one body."""
        # The barrier makes the two reservations contend instead of passing
        # through the server one after another by accident.
        barrier.wait(timeout=2)
        _, _, payload = _read(server)
        received.append(payload)

    with MockHttpServer(scripts) as server:
        threads = tuple(
            threading.Thread(target=exchange, args=(server,)) for _ in range(2)
        )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
            assert not thread.is_alive()

    assert sorted(received) == [b"left", b"right"]
    assert len(server.requests) == 2


def test_expect_continue_does_not_insert_a_status() -> None:
    """Leave every response byte to the script, including an explicit continue."""
    with MockHttpServer((_script(body=b"ready"),)) as server:
        probe = socket.create_connection((server.host, server.port), timeout=2)
        try:
            probe.sendall(
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Length: 2\r\n"
                b"Expect: 100-continue\r\n"
                b"\r\n"
                b"{}"
            )
            payload = _recv_until_closed(probe)
        finally:
            probe.close()
        recorded = server.requests

    assert payload.startswith(b"HTTP/1.1 200 ")
    assert b"HTTP/1.1 100 " not in payload
    assert payload.endswith(b"ready")
    assert recorded[0].body == b"{}"


def test_chunked_request_does_not_consume_the_script() -> None:
    """Ignore transfer encodings outside a single Content-Length body."""
    with MockHttpServer((_script(body=b"kept"),)) as server:
        probe = socket.create_connection((server.host, server.port), timeout=2)
        try:
            probe.sendall(
                b"POST /chunked HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"\r\n"
                b"0\r\n\r\n"
            )
            probe.shutdown(socket.SHUT_WR)
            assert probe.recv(64) == b""
        finally:
            probe.close()
        _, _, payload = _read(server)

    assert payload == b"kept"
    assert server.requests[0].target == "/v1/chat/completions"


def test_server_does_not_log_request_secrets() -> None:
    """Keep a credential in the request target out of the process streams."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    target = f"/v1/chat/completions?access_token={_SECRET}"

    with redirect_stdout(stdout), redirect_stderr(stderr):
        with MockHttpServer((_script(),)) as server:
            _read(server, target=target)

    # The default library log includes the request target. Silence is the
    # contract, so the placeholder must be absent from both redirected streams.
    assert _SECRET not in stdout.getvalue()
    assert _SECRET not in stderr.getvalue()
