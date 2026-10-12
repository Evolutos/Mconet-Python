"""Unary system HTTP transport over the Python standard library."""

from __future__ import annotations

import asyncio
import base64
import http.client
import os
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from typing import cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.header_field import HeaderField
from mconet.core.domain.headers import Headers
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.timestamp import Timestamp
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_request import TransportRequest
from mconet.core.spi.transport_response import TransportResponse
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata
from mconet.transport.http_system.http_body import map_http_body
from mconet.transport.http_system.http_content_length import apply_http_content_length
from mconet.transport.http_system.http_content_type import apply_http_content_type
from mconet.transport.http_system.http_deadline import ensure_http_deadline
from mconet.transport.http_system.http_default_header import apply_default_http_headers
from mconet.transport.http_system.http_header import HttpHeaderField, map_http_headers
from mconet.transport.http_system.http_method import map_http_method
from mconet.transport.http_system.http_network_timeout import (
    normalize_http_network_timeout,
)
from mconet.transport.http_system.http_proxy import (
    HttpProxyEndpoint,
    HttpProxyOverride,
    HttpProxySelection,
    select_http_proxy,
)
from mconet.transport.http_system.http_query import map_http_query
from mconet.transport.http_system.http_response_header_summary import (
    summarize_http_response_headers,
)
from mconet.transport.http_system.http_response_limit_release import (
    read_bounded_http_response_releasing_connection,
)
from mconet.transport.http_system.http_response_media_type import (
    extract_http_response_media_type,
)
from mconet.transport.http_system.http_status import map_http_status
from mconet.transport.http_system.http_tls import ensure_secure_http_tls
from mconet.transport.http_system.http_url import HttpBaseUrl, map_http_url

_READ_CHUNK_BYTES = 8192
_HTTPS_SCHEME = "https"
_NETWORK_CATEGORY = ErrorCategory(OpenIdentifier("network"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_CONNECTION_FAILED_CODE = "http_connection_failed"
_CONNECTION_FAILED_MESSAGE = "HTTP connection failed."
_CLOSED_CODE = "http_transport_closed"
_CLOSED_MESSAGE = "HTTP transport is closed."
_CONFIGURATION_CATEGORY = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_DESCRIPTOR = ComponentDescriptor(
    name="default-system-http-transport",
    version="1",
    source="builtin",
    # The snapshot factory requires a contract object. This transport has no
    # JSON data port, so the contract stays empty.
    type_contract=ComponentTypeContract(),
)


class DefaultSystemHttpTransport:
    """Send one unary HTTP request with the platform network stack.

    Redirects are returned as received. The transport does not generate the
    next request, so authorization and signature headers are not forwarded.
    Certificate verification uses the platform default context. Proxy selection
    follows the explicit override or the supplied environment. Standard-library
    connection objects stay inside this implementation. ``close`` refuses later
    exchanges. Connections opened for an exchange that already started are
    closed by that exchange, not by ``close``.
    """

    __slots__ = (
        "_closed",
        "_lock",
        "_network_client",
        "_now",
        "_proxy_environment",
        "_proxy_override",
    )

    _closed: bool
    _lock: threading.Lock
    _network_client: object | None
    _now: Callable[[], Timestamp]
    _proxy_environment: Mapping[str, str] | None
    _proxy_override: HttpProxyOverride | None

    def __init__(
        self,
        *,
        proxy_environment: Mapping[str, str] | None = None,
        proxy_override: HttpProxyOverride | None = None,
        tls_options: Mapping[str, object] | None = None,
        now: Callable[[], Timestamp] | None = None,
        network_client: object | None = None,
    ) -> None:
        """Store send policy without opening a connection.

        Args:
            proxy_environment: Proxy variables. ``None`` reads the process
                environment at send time.
            proxy_override: Explicit proxy choice that replaces the environment.
            tls_options: Optional confirmations of certificate verification.
            now: Clock used for the deadline. ``None`` uses the system clock.
            network_client: Business-owned client. ``close`` does not call it.

        Raises:
            TypeError: If an argument has an invalid shape.
            ModelInteractionError: If ``tls_options`` would disable verification.
        """
        # Reject a weakened TLS configuration before any later send can apply it.
        ensure_secure_http_tls(tls_options)
        if proxy_environment is not None and not isinstance(
            cast(object, proxy_environment), Mapping
        ):
            raise TypeError("proxy_environment must be a mapping or None.")
        if proxy_override is not None and not isinstance(
            cast(object, proxy_override), HttpProxyOverride
        ):
            raise TypeError("proxy_override must be an HttpProxyOverride or None.")
        if now is not None and not callable(cast(object, now)):
            raise TypeError("now must be callable or None.")
        if network_client is not None and not callable(
            getattr(network_client, "close", None)
        ):
            raise TypeError("network_client must provide close.")
        self._proxy_environment = proxy_environment
        self._proxy_override = proxy_override
        self._now = _system_now if now is None else now
        self._network_client = network_client
        self._lock = threading.Lock()
        self._closed = False

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the builtin transport descriptor."""
        return _DESCRIPTOR

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Send one frozen request and return the complete response bytes.

        Args:
            request: Encoded method, URL, fields, query, and body.
            context: Deadline, cancellation, and the response byte limit.

        Returns:
            Status, safe header summary, media type, and bounded body.

        Raises:
            TypeError: If ``request`` or ``context`` has an invalid shape.
            ModelInteractionError: If the transport is closed, or the request,
                deadline, proxy, or exchange fails. A platform timeout uses
                ``network_timeout``.
            asyncio.CancelledError: If the caller signal is cancelled.
        """
        self._reject_if_closed()
        self._reject_if_business_client_closed()
        prepared = _prepare_attempt(request, context)
        signal = context.cancellation
        abort = _SocketAbort()
        unsubscribe: Callable[[], None] | None = None
        if signal is not None:
            # Subscription delivers an existing cancellation before it returns,
            # so a pre-cancelled attempt does not open a connection.
            unsubscribe = signal.subscribe(abort.abort)
        try:
            if signal is not None and signal.is_cancelled:
                raise asyncio.CancelledError(_cancellation_reason(signal))
            ensure_http_deadline(context.deadline, self._now)
            environment = (
                os.environ
                if self._proxy_environment is None
                else self._proxy_environment
            )
            return await asyncio.to_thread(
                _exchange,
                prepared,
                context,
                environment,
                self._proxy_override,
                self._now,
                abort,
                signal,
            )
        finally:
            if unsubscribe is not None:
                unsubscribe()

    async def close(self) -> None:
        """Refuse later exchanges without interrupting one already started.

        Each exchange closes the connection it opened. This method does not
        close that connection again, and it does not close an injected
        ``network_client``. A second call observes the closed state and does
        not repeat a release.
        """
        with self._lock:
            self._closed = True
        # An injected client stays open. This transport does not own it.

    def _reject_if_closed(self) -> None:
        """Raise when ``close`` has already begun."""
        with self._lock:
            closed = self._closed
        if closed:
            raise _transport_closed_error()

    def _reject_if_business_client_closed(self) -> None:
        """Raise when the caller already closed the injected client."""
        client = self._network_client
        if client is None:
            return
        # Observe the business client's own flag. Do not call its close method;
        # the caller owns that resource.
        business_closed = getattr(client, "is_closed", False)
        if business_closed is True:
            raise _business_client_closed_error()


class _PreparedHttpAttempt:
    """Request fields ready for one standard-library exchange."""

    __slots__ = ("base", "body", "headers", "method", "query")

    def __init__(
        self,
        method: str,
        base: HttpBaseUrl,
        query: str,
        headers: tuple[HttpHeaderField, ...],
        body: bytes,
    ) -> None:
        self.method = method
        self.base = base
        self.query = query
        self.headers = headers
        self.body = body


class _SocketAbort:
    """Close the active connection when the caller cancels the attempt."""

    __slots__ = ("_connection",)

    def __init__(self) -> None:
        self._connection: http.client.HTTPConnection | None = None

    def arm(self, connection: http.client.HTTPConnection) -> None:
        """Retain the connection that a cancellation callback should close."""
        self._connection = connection

    def abort(self, _reason: str | None) -> None:
        """Close the armed connection, if the exchange has one."""
        # Shutdown unblocks a read in the network thread. close() alone can
        # leave that thread blocked until the peer finishes writing. The
        # reason stays on the caller signal.
        connection = self._connection
        if connection is None:
            return
        sock = connection.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()


def _prepare_attempt(
    request: TransportRequest,
    context: TransportContext,
) -> _PreparedHttpAttempt:
    """Map one frozen request onto sendable HTTP fields.

    Args:
        request: Frozen transport request.
        context: Interaction context. Its type is checked before a send.

    Returns:
        Method, base address, query, headers, and body bytes.

    Raises:
        TypeError: If ``request`` or ``context`` has an invalid shape.
        ModelInteractionError: If a mapped field cannot be sent.
    """
    if not isinstance(cast(object, request), TransportRequest):
        raise TypeError("request must be a TransportRequest.")
    if not isinstance(cast(object, context), TransportContext):
        raise TypeError("context must be a TransportContext.")
    method = map_http_method(request.method)
    base = map_http_url(request.url)
    query = map_http_query(request.query)
    body = map_http_body(request.body)
    headers = apply_http_content_length(
        apply_http_content_type(
            apply_default_http_headers(map_http_headers(request.headers)),
            request.body.media_type,
        ),
        body,
    )
    if not any(field.name.casefold() == "host" for field in headers):
        headers = (*headers, HttpHeaderField("Host", base.host))
    return _PreparedHttpAttempt(method, base, query, headers, body)


def _exchange(
    prepared: _PreparedHttpAttempt,
    context: TransportContext,
    environment: Mapping[str, str],
    override: HttpProxyOverride | None,
    now: Callable[[], Timestamp],
    abort: _SocketAbort,
    signal: CancellationSignal | None,
) -> TransportResponse:
    """Perform the blocking HTTP exchange and normalize its result.

    Args:
        prepared: Mapped request fields.
        context: Deadline and response limit for this attempt.
        environment: Proxy variables selected for this send.
        override: Explicit proxy choice, or ``None``.
        now: Clock used for the deadline.
        abort: Closer invoked by caller cancellation.
        signal: Caller cancellation signal, or ``None``.

    Returns:
        The normalized response.

    Raises:
        ModelInteractionError: If the deadline, proxy, connection, or body
            limit fails.
        asyncio.CancelledError: If the caller signal is cancelled.
    """
    _raise_if_cancelled(signal)
    ensure_http_deadline(context.deadline, now)
    selection = select_http_proxy(prepared.base, environment, override)
    connection = _open_connection(
        prepared.base,
        selection,
        _remaining_seconds(context.deadline, now),
    )
    abort.arm(connection)
    try:
        _raise_if_cancelled(signal)
        _send_request(connection, prepared, selection)
        response = connection.getresponse()
        try:
            fields = _response_header_fields(response)
            body = read_bounded_http_response_releasing_connection(
                _response_chunks(response),
                context.resource_limits.max_response_body_bytes,
                lambda: _release_exchange(response, connection),
            )
            # A short read against Content-Length is a dropped connection, not
            # a successful partial body. The received bytes are not returned.
            if _body_was_truncated(fields, body):
                raise _connection_failed()
            return _completed_response(response.status, fields, body)
        finally:
            response.close()
    except asyncio.CancelledError:
        raise
    except ModelInteractionError:
        raise
    except TimeoutError as error:
        # The socket timeout is the caller deadline when one was set. A timeout
        # with no deadline is a platform timeout and uses a different code.
        _raise_if_cancelled(signal)
        if context.deadline is not None:
            ensure_http_deadline(context.deadline, now)
        raise normalize_http_network_timeout(error) from None
    except Exception:
        if signal is not None and signal.is_cancelled:
            raise asyncio.CancelledError(_cancellation_reason(signal)) from None
        raise _connection_failed() from None
    finally:
        connection.close()


def _send_request(
    connection: http.client.HTTPConnection,
    prepared: _PreparedHttpAttempt,
    selection: HttpProxySelection,
) -> None:
    """Write the request line, headers, and body."""
    absolute = selection.endpoint is not None and prepared.base.scheme != _HTTPS_SCHEME
    target = prepared.base.href if absolute else prepared.base.path
    if prepared.query:
        target = f"{target}?{prepared.query}"
    # The library's automatic Host and Accept-Encoding would add fields this
    # transport did not prepare.
    connection.putrequest(
        prepared.method,
        target,
        skip_host=True,
        skip_accept_encoding=True,
    )
    for field in prepared.headers:
        connection.putheader(field.name, field.value)
    connection.endheaders(prepared.body)


def _open_connection(
    base: HttpBaseUrl,
    selection: HttpProxySelection,
    timeout: float | None,
) -> http.client.HTTPConnection:
    """Open a direct connection or a connection to the selected proxy."""
    endpoint = selection.endpoint
    if endpoint is None:
        host, port = _host_and_port(base.host, base.scheme)
        return _platform_connection(base.scheme, host, port, timeout)
    host, port = _host_and_port(endpoint.host, endpoint.scheme)
    connection = _platform_connection(endpoint.scheme, host, port, timeout)
    if base.scheme == _HTTPS_SCHEME:
        target_host, target_port = _host_and_port(base.host, base.scheme)
        tunnel_headers = _proxy_tunnel_headers(endpoint)
        connection.set_tunnel(target_host, target_port, headers=tunnel_headers)
    return connection


def _platform_connection(
    scheme: str,
    host: str,
    port: int,
    timeout: float | None,
) -> http.client.HTTPConnection:
    """Open one HTTP or HTTPS connection with platform TLS verification."""
    if scheme == _HTTPS_SCHEME:
        context = ssl.create_default_context()
        # The platform default is the only context this transport creates. A
        # context that does not verify the peer is not used.
        if (
            context.verify_mode != ssl.CERT_REQUIRED
            or context.check_hostname is not True
        ):
            raise _connection_failed()
        return http.client.HTTPSConnection(
            host,
            port,
            timeout=timeout,
            context=context,
        )
    return http.client.HTTPConnection(host, port, timeout=timeout)


def _proxy_tunnel_headers(endpoint: HttpProxyEndpoint) -> dict[str, str] | None:
    """Return proxy credentials for a tunnel, not for the origin request."""
    if endpoint.username is None:
        return None
    password = "" if endpoint.password is None else endpoint.password
    token = base64.b64encode(f"{endpoint.username}:{password}".encode()).decode("ascii")
    return {"Proxy-Authorization": f"Basic {token}"}


def _response_chunks(response: http.client.HTTPResponse) -> Iterator[bytes]:
    """Yield response body chunks without reading the remainder first."""
    while True:
        chunk = response.read(_READ_CHUNK_BYTES)
        if chunk == b"":
            break
        yield chunk


def _response_header_fields(
    response: http.client.HTTPResponse,
) -> tuple[HttpHeaderField, ...]:
    """Copy response header pairs without retaining the library message."""
    raw = cast(object, getattr(response.headers, "_headers", ()))
    if not isinstance(raw, list):
        return ()
    fields: list[HttpHeaderField] = []
    for item in cast(list[object], raw):
        if not isinstance(item, tuple):
            continue
        pair = cast(tuple[object, ...], item)
        if (
            len(pair) != 2
            or not isinstance(pair[0], str)
            or not isinstance(pair[1], str)
        ):
            continue
        fields.append(HttpHeaderField(pair[0], pair[1]))
    return tuple(fields)


def _body_was_truncated(
    fields: tuple[HttpHeaderField, ...],
    body: bytes,
) -> bool:
    """Return whether one Content-Length does not match the received body."""
    lengths = tuple(
        field.value for field in fields if field.name.casefold() == "content-length"
    )
    if len(lengths) != 1 or not lengths[0].isdigit():
        return False
    return len(body) != int(lengths[0])


def _completed_response(
    status_code: int,
    fields: tuple[HttpHeaderField, ...],
    body: Bytes,
) -> TransportResponse:
    """Build the public response from a received status, headers, and body."""
    classified = map_http_status(status_code)
    safe_headers = summarize_http_response_headers(fields)
    return TransportResponse(
        response_metadata=TransportResponseMetadata(
            outcome=classified.outcome,
            headers=Headers(
                tuple(HeaderField(field.name, field.value) for field in safe_headers)
            ),
            status_code=classified.status_code,
            media_type=extract_http_response_media_type(fields),
        ),
        body=body,
    )


def _release_exchange(
    response: http.client.HTTPResponse,
    connection: http.client.HTTPConnection,
) -> None:
    """Stop the response read and drop the connection after a size limit."""
    response.close()
    connection.close()


def _host_and_port(host: str, scheme: str) -> tuple[str, int]:
    """Split a mapped host token into a connection hostname and port."""
    if host.startswith("["):
        bracket = host.find("]")
        name = host[1:bracket]
        port_text = (
            host[bracket + 2 :] if host[bracket + 1 : bracket + 2] == ":" else ""
        )
    else:
        name, separator, port_text = host.rpartition(":")
        if separator == "" or not port_text.isdigit():
            name = host
            port_text = ""
    if port_text == "":
        return name, 443 if scheme == _HTTPS_SCHEME else 80
    return name, int(port_text)


def _remaining_seconds(
    deadline: Timestamp | None,
    now: Callable[[], Timestamp],
) -> float | None:
    """Return the socket timeout implied by the deadline, or no timeout."""
    if deadline is None:
        return None
    current = now()
    seconds = (deadline.epoch_seconds - current.epoch_seconds) + (
        deadline.nanosecond - current.nanosecond
    ) / 1_000_000_000
    return max(seconds, 0.0)


def _system_now() -> Timestamp:
    """Return the current UTC instant at nanosecond resolution."""
    seconds = time.time()
    epoch_seconds = int(seconds)
    nanosecond = int((seconds - epoch_seconds) * 1_000_000_000)
    return Timestamp(epoch_seconds=epoch_seconds, nanosecond=nanosecond)


def _raise_if_cancelled(signal: CancellationSignal | None) -> None:
    """Raise when the caller signal has already been cancelled."""
    if signal is not None and signal.is_cancelled:
        raise asyncio.CancelledError(_cancellation_reason(signal))


def _cancellation_reason(signal: CancellationSignal) -> str | None:
    """Return the signal reason when it is text."""
    reason = signal.reason
    if isinstance(reason, str):
        return reason
    return None


def _business_client_closed_error() -> ModelInteractionError:
    """Create the failure for a send whose injected client is already closed."""
    return ModelInteractionError(
        category=_CONFIGURATION_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code="http_network_client_closed",
        message="Injected HTTP client is closed.",
    )


def _transport_closed_error() -> ModelInteractionError:
    """Create the failure for a send after close."""
    return ModelInteractionError(
        category=_CONFIGURATION_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_CLOSED_CODE,
        message=_CLOSED_MESSAGE,
    )


def _connection_failed() -> ModelInteractionError:
    """Create a connection failure that does not include the destination."""
    # Platform messages can include the host, proxy, or a certificate path.
    return ModelInteractionError(
        category=_NETWORK_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_CONNECTION_FAILED_CODE,
        message=_CONNECTION_FAILED_MESSAGE,
    )
