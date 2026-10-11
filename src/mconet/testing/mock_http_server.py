"""Local loopback HTTP server with one ordered response script."""

from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from email.message import Message
from http.client import responses
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

from mconet.core.domain import (
    Bytes,
    Duration,
    HeaderField,
    Headers,
    UriValue,
    validate_uri,
)

_HOST = "127.0.0.1"
_ZERO_DELAY = Duration(0)
_EMPTY_HEADERS = Headers()
_MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024
_ABORT_POINTS = frozenset({"before_response", "after_headers", "during_body"})
_HEADER_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_CONTENT_LENGTH = "content-length"
_TRANSFER_ENCODING = "transfer-encoding"


@dataclass(frozen=True, slots=True)
class MockHttpAbort:
    """Identify where a scripted response cuts the HTTP connection.

    ``before_response`` closes after the request is read and before any response
    byte. ``after_headers`` writes the status line and headers, then closes
    before the promised body. ``during_body`` writes a strict prefix of the body
    and then closes. These are the only points a later system HTTP transport
    needs in order to observe a dropped connection separately from an HTTP
    status.
    """

    point: str
    """One of ``before_response``, ``after_headers``, or ``during_body``."""

    def __post_init__(self) -> None:
        """Reject unknown cut points before a server can bind a socket."""
        point = cast(object, self.point)
        # An exact string keeps bool and other subclasses from selecting a cut
        # accidentally, and the closed set prevents a typo from becoming a
        # normal completed response.
        if type(point) is not str:
            raise TypeError("abort point must be a string.")
        if point not in _ABORT_POINTS:
            raise ValueError("abort point is not supported.")


@dataclass(frozen=True, slots=True)
class MockHttpResponseScript:
    """One ordered HTTP response emitted for the next accepted request.

    Header order and repeated names are preserved. When ``Content-Length`` is
    absent, the server appends the full body length so a client can detect a
    later cut. A scripted ``Content-Length`` is sent unchanged, which is what
    makes a short transmission observable as an incomplete body.

    The script does not interpret status codes, follow redirects, or encode a
    model payload. Delay is applied after the request is recorded and before
    the first response byte.
    """

    status_code: int
    """HTTP status written on the status line when the response is not cut."""

    headers: Headers = _EMPTY_HEADERS
    """Response fields, excluding the ``Content-Length`` the server may append."""

    body: bytes = b""
    """Full response body. An abort may transmit only a prefix."""

    delay: Duration = _ZERO_DELAY
    """Non-negative wait between recording the request and writing a response."""

    abort: MockHttpAbort | None = None
    """Optional connection cut. ``None`` writes the status, headers, and body."""

    body_prefix_length: int | None = None
    """Bytes written before a ``during_body`` cut. Required only for that cut."""

    def __post_init__(self) -> None:
        """Reject a script that cannot produce an observable HTTP exchange."""
        status_code = cast(object, self.status_code)
        headers = cast(object, self.headers)
        body = cast(object, self.body)
        delay = cast(object, self.delay)
        abort = cast(object, self.abort)
        prefix = cast(object, self.body_prefix_length)

        # Validate the whole script before the server listens. A late failure
        # would otherwise look like the connection cut this object is meant to
        # script deliberately.
        if type(status_code) is not int:
            raise TypeError("status_code must be an integer.")
        if not 100 <= status_code <= 599:
            raise ValueError("status_code must be in the range 100..599.")
        if not isinstance(headers, Headers):
            raise TypeError("headers must be Headers.")
        if not isinstance(body, bytes):
            raise TypeError("body must be bytes.")
        if not isinstance(delay, Duration):
            raise TypeError("delay must be a Duration.")
        if delay.total_nanoseconds < 0:
            raise ValueError("delay must not be negative.")
        if abort is not None and not isinstance(abort, MockHttpAbort):
            raise TypeError("abort must be a MockHttpAbort or None.")
        if prefix is not None and type(prefix) is not int:
            raise TypeError("body_prefix_length must be an integer or None.")

        for field in headers.values:
            _validate_response_header(field)
        content_length = _scripted_content_length(headers)
        _validate_abort(abort, body, prefix, content_length)


@dataclass(frozen=True, slots=True)
class MockHttpRequest:
    """One complete inbound HTTP request recorded before the scripted delay."""

    method: str
    """Request method as parsed from the request line."""

    target: str
    """Request target, including the query string when present."""

    http_version: str
    """Protocol version token from the request line, such as ``HTTP/1.1``."""

    headers: Headers
    """Parsed header fields in wire order, including repeated names."""

    body: Bytes
    """Bytes read for ``Content-Length``. Absent length yields an empty body."""

    def __post_init__(self) -> None:
        """Require the parsed request to remain an immutable value object."""
        method = cast(object, self.method)
        target = cast(object, self.target)
        http_version = cast(object, self.http_version)
        headers = cast(object, self.headers)
        body = cast(object, self.body)

        # The handler builds these values, but the object still owns its
        # contract so a partial parse cannot enter the recorded exchange list.
        if type(method) is not str or not method:
            raise TypeError("method must be a non-empty string.")
        if type(target) is not str or not target:
            raise TypeError("target must be a non-empty string.")
        if type(http_version) is not str or not http_version:
            raise TypeError("http_version must be a non-empty string.")
        if not isinstance(headers, Headers):
            raise TypeError("headers must be Headers.")
        if not isinstance(body, bytes):
            raise TypeError("body must be bytes.")


class _ExchangeLedger:
    """Reserve script entries and retain the first handler failure.

    The handler thread calls this object directly. Keeping the methods on a
    private type avoids exposing reservation on the public server while still
    letting the handler reach them under Pyright's protected-name rules.
    """

    __slots__ = ("_condition", "_failures", "_next_index", "_requests", "_scripts")

    def __init__(self, scripts: tuple[MockHttpResponseScript, ...]) -> None:
        """Retain the immutable script and empty exchange state.

        Args:
            scripts: Snapshot already validated by the public server.
        """
        # The lock and counters belong to this script only. Two servers in one
        # process must not share reservation order.
        self._condition = threading.Condition()
        self._scripts = scripts
        self._requests: list[MockHttpRequest] = []
        self._failures: list[BaseException] = []
        self._next_index = 0

    def requests(self) -> tuple[MockHttpRequest, ...]:
        """Return a stable copy of requests in reservation order."""
        with self._condition:
            # Copy under the reservation lock so the snapshot is one complete
            # prefix even while another thread accepts the next request.
            return tuple(self._requests)

    def reserve(self, request: MockHttpRequest) -> MockHttpResponseScript | None:
        """Record one request and reserve its script, if any remain."""
        with self._condition:
            # Reservation is the concurrency boundary. Recording the request
            # first keeps an exhausted call visible to the test that caused it.
            self._requests.append(request)
            index = self._next_index
            if index >= len(self._scripts):
                self._failures.append(
                    AssertionError("scripted HTTP exchanges are exhausted.")
                )
                return None
            self._next_index = index + 1
            return self._scripts[index]

    def note_failure(self, failure: BaseException) -> None:
        """Retain the earliest unexpected handler failure."""
        with self._condition:
            # Keep the earliest failure so a later disconnect caused by that
            # failure does not replace the original explanation.
            if not self._failures:
                self._failures.append(failure)

    def first_failure(self) -> BaseException | None:
        """Return the first retained failure after handlers have stopped."""
        with self._condition:
            # Return the original instance. close raises it unchanged so a test
            # can match the exhaustion or handler failure directly.
            if not self._failures:
                return None
            return self._failures[0]


class MockHttpServer:
    """Serve scripted HTTP exchanges on loopback for transport fault tests.

    Each accepted connection reads one request, records it, waits for that
    script's delay, and then writes or cuts the connection. Script order follows
    reservation order under one lock. An extra request after the script is
    exhausted is still recorded, and :meth:`close` raises so the extra exchange
    cannot pass silently.

    This is a real ``HTTP/1.1`` peer bound only to ``127.0.0.1``. It is not a
    ``Transport`` double: ``MockTransport`` covers in-process dispatch, while
    this server exists so a system HTTP client can observe status, headers,
    body bytes, delay, and a dropped socket. The server does not add ``Server``
    or ``Date`` fields, does not log headers or bodies, and does not follow
    redirects or interpret model payloads.

    Each instance can be entered once. Connections are not kept alive, so one
    request consumes one script entry. Request bodies must use ``Content-Length``
    and cannot exceed 8 MiB.
    """

    __slots__ = (
        "_closed",
        "_httpd",
        "_ledger",
        "_lifecycle",
        "_started",
        "_thread",
    )

    def __init__(self, scripts: Sequence[MockHttpResponseScript]) -> None:
        """Snapshot the ordered response script before listening.

        Args:
            scripts: Non-empty sequence consumed once, in order, per request.

        Raises:
            TypeError: If ``scripts`` or any entry has an invalid runtime type.
            ValueError: If ``scripts`` is empty.
        """
        scripts_value = cast(object, scripts)
        if not isinstance(scripts_value, Sequence) or isinstance(
            scripts_value, (str, bytes, bytearray)
        ):
            raise TypeError("scripts must be an ordered sequence.")

        # Copy before the socket exists so a caller cannot append another
        # exchange, or replace one, after a test has started the server.
        snapshot = tuple(cast(Sequence[object], scripts_value))
        if not snapshot:
            raise ValueError("at least one HTTP exchange must be scripted.")
        for script in snapshot:
            if not isinstance(script, MockHttpResponseScript):
                raise TypeError("scripts must contain MockHttpResponseScript values.")

        self._ledger = _ExchangeLedger(
            cast(tuple[MockHttpResponseScript, ...], snapshot)
        )
        self._lifecycle = threading.Lock()
        self._httpd: _LoopbackHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._started = False
        self._closed = False

    @property
    def host(self) -> str:
        """Return the loopback address this server binds."""
        # The address is fixed so a test cannot retarget the peer onto another
        # interface. It does not by itself mean the socket is listening.
        return _HOST

    @property
    def port(self) -> int:
        """Return the ephemeral port selected when the server started.

        Raises:
            RuntimeError: If the server is not currently started.
        """
        address = self._require_httpd().server_address
        port = address[1]
        # The standard library address pair is untyped at the boundary. Require
        # the integer port before a client builds a URI from it.
        if type(port) is not int:
            raise RuntimeError("MockHttpServer did not bind an integer port.")
        return port

    @property
    def uri(self) -> UriValue:
        """Return the absolute loopback URI for the listening server.

        Raises:
            RuntimeError: If the server is not currently started.
        """
        # Validate the generated URI so a binding change cannot publish a value
        # the rest of the SDK would later reject.
        return validate_uri(UriValue(f"http://{_HOST}:{self.port}/", True))

    @property
    def requests(self) -> tuple[MockHttpRequest, ...]:
        """Return recorded requests in script reservation order."""
        # The ledger owns the lock. Delegating keeps this snapshot aligned with
        # the reservation order the handler just committed.
        return self._ledger.requests()

    def __enter__(self) -> MockHttpServer:
        """Bind the loopback socket and start accepting connections.

        Returns:
            This server, after its port is known.

        Raises:
            RuntimeError: If this instance was already started.
            OSError: If the loopback socket cannot be bound.
        """
        with self._lifecycle:
            # One socket per instance keeps close() deterministic. A second
            # entry would otherwise orphan the first listening thread.
            if self._started or self._closed:
                raise RuntimeError("MockHttpServer can only be started once.")
            self._started = True

        httpd = _LoopbackHttpServer(self._ledger)
        thread = threading.Thread(
            target=httpd.serve_forever,
            name="mconet-mock-http",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            # The listening socket already exists once the server object is
            # constructed, so a failed thread start must still release it.
            httpd.server_close()
            with self._lifecycle:
                self._closed = True
            raise

        with self._lifecycle:
            self._httpd = httpd
            self._thread = thread
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Stop the listener without hiding an exception from the block."""
        del exc, traceback
        # A failure already leaving the block is the one the test observed.
        # Script exhaustion is reported only when the block itself completed.
        failure = self._stop()
        if exc_type is None and failure is not None:
            raise failure

    def close(self) -> None:
        """Stop accepting connections and raise the first script failure.

        The call waits for request threads already inside a scripted delay.
        A second call is a no-op so cleanup stays idempotent.

        Raises:
            BaseException: The first exhaustion or unexpected handler failure.
            RuntimeError: If the listening thread does not stop.
        """
        # Explicit close has no surrounding test exception to preserve, so a
        # script failure becomes this call's result.
        failure = self._stop()
        if failure is not None:
            raise failure

    def _stop(self) -> BaseException | None:
        """Release the listener and return the first retained script failure."""
        with self._lifecycle:
            if self._closed:
                return None
            # Mark closed before joining. Handlers already past this point may
            # finish one reservation, and shutdown unblocks the acceptor.
            self._closed = True
            httpd = self._httpd
            thread = self._thread

        if httpd is not None:
            # shutdown() must run outside the ledger lock: a handler can be
            # waiting for that lock while this thread waits for the handler.
            httpd.shutdown()
            httpd.server_close()
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("MockHttpServer did not stop.")
        return self._ledger.first_failure()

    def _require_httpd(self) -> _LoopbackHttpServer:
        """Return the live listener or explain that it is not started."""
        with self._lifecycle:
            httpd = self._httpd
            closed = self._closed
        if httpd is None or closed:
            raise RuntimeError("MockHttpServer is not running.")
        return httpd


class _LoopbackHttpServer(ThreadingHTTPServer):
    """Bind one loopback listener whose handler reads the owning script."""

    daemon_threads = False
    allow_reuse_address = True

    def __init__(self, ledger: _ExchangeLedger) -> None:
        """Bind ``127.0.0.1`` on an ephemeral port.

        Args:
            ledger: Script and request state shared with the public server.
        """
        self.ledger = ledger
        # Binding happens here, before the accept thread starts, so the public
        # port is known as soon as enter returns.
        super().__init__((_HOST, 0), _ScriptedHandler)


class _ScriptedHandler(BaseHTTPRequestHandler):
    """Apply one reserved script to a single parsed HTTP request."""

    protocol_version = "HTTP/1.1"
    timeout = 5

    def handle_one_request(self) -> None:
        """Parse one request and dispatch it without inventing an HTTP status."""
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ""
                self.request_version = ""
                self.command = ""
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                # parse_request already wrote its own rejection. It did not
                # reserve a script, so the next valid request keeps its place.
                return
            # _respond flushes or cuts the socket itself. A second flush here
            # would turn an intentional cut into an unexpected handler error.
            self._respond()
        except TimeoutError:
            # A client that stalls while sending the request must not pin a
            # handler thread. This is independent of a scripted response delay.
            self.close_connection = True
        except Exception as error:
            # Keep the traceback off stderr. Request targets and headers can
            # carry credentials, and the server promises not to log them.
            self.close_connection = True
            self._ledger().note_failure(error)
            self._cut()

    def handle_expect_100(self) -> bool:
        """Accept ``Expect`` without writing an automatic ``100`` response."""
        # The script owns every response byte. An implicit continue would add
        # a status the test did not script and would change abort timing.
        return True

    def log_message(self, format: str, *args: object) -> None:
        """Drop stdlib request logs so headers and targets never reach stderr."""
        # The stdlib would interpolate the request target into stderr. Dropping
        # the format and values keeps credentials out of the process log.
        del format, args

    def _respond(self) -> None:
        """Record the request, wait, then write or cut the scripted response."""
        request = self._read_request()
        if request is None:
            # A rejected request is not an exchange. Leave the script in place
            # for the next complete request and close this connection.
            self._cut()
            return

        script = self._ledger().reserve(request)
        if script is None:
            self._cut()
            return

        # Delay runs outside the reservation lock so another connection can
        # reserve the next script while this response is still waiting.
        _wait(script.delay)
        if script.abort is not None and script.abort.point == "before_response":
            self._cut()
            return
        self._write_response(script)
        # One script entry is one connection. Keep-alive would let a second
        # request on this socket consume another entry before the client
        # observed the first close.
        self.close_connection = True

    def _read_request(self) -> MockHttpRequest | None:
        """Return one complete request, or ``None`` when it must be ignored."""
        try:
            body = self._read_body()
        except ValueError:
            return None

        command = self.command
        target = self.path
        version = self.request_version
        # An empty request line would not identify an exchange. parse_request
        # normally prevents that; the check keeps a blank line out of the log.
        if not command or not target or not version:
            return None
        return MockHttpRequest(
            command,
            target,
            version,
            _header_message(self.headers),
            Bytes(body),
        )

    def _read_body(self) -> bytes:
        """Read a bounded ``Content-Length`` body.

        Raises:
            ValueError: If the request declares chunked transfer or an unusable
                length. The caller treats that as a rejected request.
        """
        headers = self.headers
        if headers.get(_TRANSFER_ENCODING) is not None:
            # R1 writes a complete byte body with Content-Length. Accepting
            # chunked framing here would require a second parser and could
            # desynchronize the next scripted exchange.
            raise ValueError("Transfer-Encoding is not supported.")

        raw_lengths = headers.get_all(_CONTENT_LENGTH)
        if not raw_lengths:
            return b""
        if len(raw_lengths) != 1 or not raw_lengths[0].isdigit():
            raise ValueError("Content-Length must be one non-negative integer.")

        length = int(raw_lengths[0])
        if length > _MAX_REQUEST_BODY_BYTES:
            raise ValueError("Content-Length exceeds the request body limit.")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("request body ended before Content-Length.")
        return body

    def _write_response(self, script: MockHttpResponseScript) -> None:
        """Write the status, scripted headers, and the bytes selected by abort."""
        reason = responses.get(script.status_code, "Unknown")
        wire_headers = _wire_headers(script)
        # Latin-1 matches the header values accepted at script construction.
        # The body is written separately so arbitrary octets stay intact.
        header_block = bytearray()
        header_block.extend(
            f"HTTP/1.1 {script.status_code} {reason}\r\n".encode("ascii")
        )
        for field in wire_headers:
            header_block.extend(f"{field.name}: {field.value}\r\n".encode("latin-1"))
        header_block.extend(b"\r\n")
        self.wfile.write(header_block)

        if script.abort is not None and script.abort.point == "after_headers":
            self.wfile.flush()
            self._cut()
            return

        if script.abort is not None and script.abort.point == "during_body":
            prefix_length = script.body_prefix_length
            if type(prefix_length) is not int:
                # Construction rejects this shape. The branch avoids writing
                # the full body if a script is ever built by bypassing it.
                self._ledger().note_failure(
                    RuntimeError("during_body abort is missing a prefix length.")
                )
                self._cut()
                return
            self.wfile.write(script.body[:prefix_length])
            self.wfile.flush()
            self._cut()
            return

        self.wfile.write(script.body)
        self.wfile.flush()

    def _cut(self) -> None:
        """Finish the HTTP connection without further response bytes."""
        self.close_connection = True
        try:
            self.wfile.flush()
        except OSError:
            # The peer may already have gone away. The cut is still complete
            # from this side, so the socket error is not a script failure.
            return
        try:
            self.connection.shutdown(socket.SHUT_WR)
        except OSError:
            return

    def _ledger(self) -> _ExchangeLedger:
        """Return the script ledger carried by the loopback server."""
        server = cast(_LoopbackHttpServer, self.server)
        # The handler class is installed only on _LoopbackHttpServer, which
        # always sets the ledger before any connection is accepted.
        return server.ledger


def _validate_response_header(field: HeaderField) -> None:
    """Reject a response field that cannot be written as one HTTP line."""
    if _HEADER_TOKEN.fullmatch(field.name) is None:
        raise ValueError("header name must be an HTTP token.")
    try:
        encoded = field.value.encode("latin-1")
    except UnicodeEncodeError as error:
        raise ValueError("header value must be Latin-1.") from error
    # CR and LF would split the field into another header. Other controls are
    # rejected for the same reason, while tab remains a legal field character.
    if any((byte < 0x20 and byte != 0x09) or byte == 0x7F for byte in encoded):
        raise ValueError("header value contains a control character.")


def _scripted_content_length(headers: Headers) -> int | None:
    """Return one scripted content length, if the script declared it."""
    values = headers.get_all("Content-Length")
    # Repeated or non-decimal lengths would make a later cut ambiguous, because
    # the client would not know how many body bytes were promised.
    if not values:
        return None
    if len(values) != 1 or not values[0].isdigit():
        raise ValueError("Content-Length must be one non-negative integer.")
    return int(values[0])


def _validate_abort(
    abort: MockHttpAbort | None,
    body: bytes,
    prefix: int | None,
    content_length: int | None,
) -> None:
    """Require each cut to withhold at least one promised body byte."""
    if abort is None:
        if prefix is not None:
            raise ValueError("body_prefix_length requires a during_body abort.")
        return

    if abort.point != "during_body":
        if prefix is not None:
            raise ValueError("body_prefix_length requires a during_body abort.")
        if abort.point == "after_headers":
            declared = len(body) if content_length is None else content_length
            # A zero promised length followed by an immediate close is a normal
            # empty response, so it cannot stand in for a cut stream.
            if declared <= 0:
                raise ValueError("after_headers abort must promise a body.")
        return

    if prefix is None:
        raise ValueError("during_body abort requires body_prefix_length.")
    declared = len(body) if content_length is None else content_length
    # The prefix must be a real partial send: at least one body byte, and
    # strictly fewer bytes than the length the response promises.
    if prefix <= 0 or prefix > len(body) or prefix >= declared:
        raise ValueError("body_prefix_length must withhold part of the body.")


def _wire_headers(script: MockHttpResponseScript) -> tuple[HeaderField, ...]:
    """Return scripted fields plus a content length when the script omitted one."""
    if script.headers.get_all("Content-Length"):
        return script.headers.values
    # The appended length is the full scripted body, including bytes a cut
    # will not send. The client observes that shortage as a dropped stream.
    return (
        *script.headers.values,
        HeaderField("Content-Length", str(len(script.body))),
    )


def _header_message(message: Message[str, str]) -> Headers:
    """Copy parsed request fields without combining repeated names."""
    fields: list[HeaderField] = []
    for name, value in message.items():
        # Message.items preserves each occurrence. Wrapping them in the domain
        # collection keeps later assertions independent of the parser type.
        fields.append(HeaderField(str(name), str(value)))
    return Headers(tuple(fields))


def _wait(delay: Duration) -> None:
    """Block until at least ``delay`` has elapsed on the monotonic clock."""
    if delay.total_nanoseconds == 0:
        return
    # sleep may return early. Looping to a monotonic deadline makes the
    # scripted delay a lower bound rather than a single kernel request.
    deadline = time.monotonic() + (delay.total_nanoseconds / 1_000_000_000)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(remaining)
