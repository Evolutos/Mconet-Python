"""Server-stream execution for the public client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.media_type import MediaType
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.server_stream import ServerStream
from mconet.core.domain.server_stream_event import ServerStreamEvent
from mconet.core.domain.uri import UriValue
from mconet.core.runtime._authorization_application import apply_authorization_handler
from mconet.core.runtime._authorization_handler_resolution import (
    resolve_interaction_authorization_handler,
)
from mconet.core.runtime._authorization_will_resolve import (
    publish_authorization_will_resolve,
)
from mconet.core.runtime._cancellation_resolution import resolve_cancellation_signal
from mconet.core.runtime._component_selection_schedule import (
    select_execution_components,
)
from mconet.core.runtime._configuration_resolution import (
    resolve_interaction_configuration,
)
from mconet.core.runtime._credential_read import read_interaction_credential
from mconet.core.runtime._deadline_resolution import resolve_transport_context
from mconet.core.runtime._error_outcome_branch import resolve_error_outcome_decoder
from mconet.core.runtime._execution_snapshot_schedule import (
    freeze_interaction_execution_components,
)
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime._interaction_runtime import (
    default_sdk_resource_limits,
    empty_sdk_components,
    http_transport_kind,
    interaction_timestamp,
    merge_interaction_monitors,
    select_authorization_handlers,
    select_authorization_resolver,
    select_interaction_integration_plan,
    select_service_access_resolver,
)
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._monitor_failure_isolation import (
    publish_isolated_monitor_chain,
)
from mconet.core.runtime._payload_decoding import decode_response_payload
from mconet.core.runtime._payload_encoding import encode_protocol_payload
from mconet.core.runtime._pre_authorization_snapshot_schedule import (
    create_pre_authorization_snapshot,
)
from mconet.core.runtime._protocol_plan_preparation import (
    prepare_protocol_execution_plan,
)
from mconet.core.runtime._protocol_plan_scope import (
    validate_server_stream_protocol_execution_plan,
)
from mconet.core.runtime._protocol_request_build import build_protocol_request
from mconet.core.runtime._r1_validation import validate_server_stream_interaction
from mconet.core.runtime._response_resource_release import ResponseResources
from mconet.core.runtime._server_stream_framing import iter_sse_payloads
from mconet.core.runtime._service_access_resolution import resolve_service_access
from mconet.core.runtime._service_error_parsing import parse_service_error
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.spi.authorization_context import AuthorizationContext
from mconet.core.spi.interaction_execution_components import (
    InteractionExecutionComponents,
)
from mconet.core.spi.interaction_monitor import InteractionMonitor
from mconet.core.spi.interaction_options import InteractionOptions
from mconet.core.spi.model_client_configuration import ModelClientConfiguration
from mconet.core.spi.monitoring_event import MonitoringEvent
from mconet.core.spi.mutable_transport_request import MutableTransportRequest
from mconet.core.spi.protocol_execution_plan import ProtocolExecutionPlan
from mconet.core.spi.runtime_components import RuntimeComponents
from mconet.core.spi.transport import Transport
from mconet.core.spi.transport_context import TransportContext
from mconet.core.spi.transport_request import TransportRequest
from mconet.core.spi.transport_request_plan import TransportRequestPlan
from mconet.core.spi.transport_response_metadata import TransportResponseMetadata

_UNSUPPORTED = ErrorCategory(OpenIdentifier("unsupported_feature"))
_PROTOCOL = ErrorCategory(OpenIdentifier("protocol"))
_PLANNING = InteractionPhase(OpenIdentifier("protocol_planning"))
_FRAMING = InteractionPhase(OpenIdentifier("stream_framing"))
_SUCCESS = OpenIdentifier("success")
_SERVER_STREAM_MODE_ID = OpenIdentifier("server_stream")
_MAPPER_KEY = "mconet.server_stream.mapper"
_MISSING_MAPPER_CODE = "unsupported_protocol_plan"
_MISSING_MAPPER_MESSAGE = (
    "The execution plan does not provide a server-stream event mapper."
)
_MISSING_TRANSPORT_CODE = "unsupported_interaction_mode"
_MISSING_TRANSPORT_MESSAGE = "The selected transport cannot open a server stream."
_MEDIA_TYPE_CODE = "response_media_type_mismatch"
_MEDIA_TYPE_MESSAGE = "The server stream media type is not text/event-stream."


@dataclass(frozen=True, slots=True)
class _ServerStreamMode:
    """Name the server-stream execution mode selected by this runtime."""

    @property
    def id(self) -> OpenIdentifier:
        """Return the server-stream mode identifier."""
        # The mode object exists so validation compares an identifier rather
        # than a private string stored on the runtime.
        return _SERVER_STREAM_MODE_ID


_SERVER_STREAM_MODE = _ServerStreamMode()


class _OpenedServerStream(Protocol):
    """The headers and body chunks returned by a streaming transport."""

    metadata: TransportResponseMetadata

    def close(self) -> None:
        """Stop the body read."""
        # The concrete stream aborts the socket. This protocol only names that step.
        ...

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Return the body chunks."""
        # The concrete stream yields the chunks already queued by the worker.
        ...


class _Release:
    """Close one opened stream and drop interaction state exactly once."""

    __slots__ = ("_closed", "_context", "_opened", "_resources")

    def __init__(
        self,
        opened: object,
        context: InteractionContext,
        resources: ResponseResources,
    ) -> None:
        """Retain the exchange and the state released with it."""
        # Close stays false until the first call so construction does not
        # release a stream the caller has not started reading.
        self._opened = opened
        self._context = context
        self._resources = resources
        self._closed = False

    def __call__(self) -> None:
        """Abort the exchange and release retained interaction state."""
        # Iteration, explicit close, and garbage collection can all reach this
        # closer. The flag makes those paths share one release.
        if self._closed:
            return
        self._closed = True
        closer = getattr(self._opened, "close", None)
        if callable(closer):
            closer()
        self._resources.release()
        if not self._context.released:
            self._context.release()


async def execute_server_stream(
    request: ModelRequest,
    options: InteractionOptions,
    configuration: ModelClientConfiguration,
    sdk_defaults: RuntimeComponents | None = None,
) -> ServerStream:
    """Open one server stream and return its single-consumption event source.

    Configuration, integration, encoding, and authorization follow the unary
    pipeline. The transport then opens a server stream instead of buffering
    one JSON body. A non-success status is parsed as a service error before
    any event is returned. A success status must be ``text/event-stream``.

    Args:
        request: Complete model request for this interaction.
        options: Overrides that apply only to this interaction.
        configuration: Reusable client defaults. This object is not modified.
        sdk_defaults: SDK-owned components. None uses an empty carrier.

    Returns:
        A stream that yields one event per mapped SSE payload and a terminal
        event when the body is finished.

    Raises:
        TypeError: If an argument has an invalid nominal type.
        ValueError: If configuration cannot produce a target or limits.
        ModelInteractionError: If a stage rejects the interaction, the
            transport cannot stream, or the response is a service error.
    """
    candidate_request = cast(object, request)
    candidate_options = cast(object, options)
    candidate_configuration = cast(object, configuration)
    if not isinstance(candidate_request, ModelRequest):
        raise TypeError("request must be a ModelRequest.")
    if not isinstance(candidate_options, InteractionOptions):
        raise TypeError("options must be an InteractionOptions.")
    if not isinstance(candidate_configuration, ModelClientConfiguration):
        raise TypeError("configuration must be a ModelClientConfiguration.")
    candidate_defaults = cast(object, sdk_defaults)
    if candidate_defaults is None:
        candidate_defaults = empty_sdk_components()
    elif not isinstance(candidate_defaults, RuntimeComponents):
        raise TypeError("sdk_defaults must be RuntimeComponents or None.")

    interaction_layer = InteractionConfigurationLayer(
        service_access=candidate_options.service_access_override,
        compatibility_policy=candidate_options.compatibility_policy,
        resource_limits=candidate_options.resource_limits,
        cancellation_signal=candidate_options.cancellation_signal,
    )
    client_layer = InteractionConfigurationLayer(
        target=candidate_configuration.default_target,
        service_access=candidate_configuration.default_service_access,
        compatibility_policy=candidate_configuration.default_compatibility_policy,
        resource_limits=candidate_configuration.default_resource_limits,
    )
    # The server-stream gate replaces the unary mode gate. Task, artifact, and
    # text checks stay the same, and they still run before any merge.
    resolved = resolve_interaction_configuration(
        candidate_request,
        _SERVER_STREAM_MODE,
        interaction_layer=interaction_layer,
        client_layer=client_layer,
        integration_layer=InteractionConfigurationLayer(),
        sdk_resource_limits=default_sdk_resource_limits(),
        interaction_validation=validate_server_stream_interaction,
    )
    context = InteractionContext(candidate_request, resolved)
    opened: object | None = None
    try:
        plan = select_interaction_integration_plan(
            candidate_request,
            candidate_options,
            candidate_configuration,
            resolved.compatibility_policy,
            _SERVER_STREAM_MODE,
        )
        access_resolver = select_service_access_resolver(
            candidate_options,
            candidate_configuration,
        )
        access = resolve_service_access(
            access_resolver,
            candidate_request,
            plan,
            interaction_layer=interaction_layer,
            client_layer=client_layer,
        )
        execution_plan = prepare_protocol_execution_plan(
            candidate_request,
            access,
            _SERVER_STREAM_MODE,
            plan,
        )
        mapper = _event_mapper(execution_plan)
        selection = select_execution_components(
            _SERVER_STREAM_MODE,
            execution_plan,
            plan,
            interaction_components=candidate_options.components,
            client_components=candidate_configuration.components,
            sdk_defaults=candidate_defaults,
            plan_scope=validate_server_stream_protocol_execution_plan,
        )
        components = freeze_interaction_execution_components(
            integration_plan=plan,
            component_selection=selection,
            resource_limits=resolved.resource_limits,
            service_access_resolver=access_resolver,
            authorization_handler_resolver=select_authorization_resolver(
                candidate_options,
                candidate_configuration,
            ),
            authorization_handlers=select_authorization_handlers(
                candidate_options,
                candidate_configuration,
                candidate_defaults,
                plan,
            ),
            requirements=(),
        )
        # A unary transport can still be selected for HTTP. Streaming requires
        # the extra open operation, and that check happens before credentials
        # are applied to a request that cannot be sent as a stream.
        opener = _server_stream_opener(components.transport)
        interaction_id = str(context.identity)
        now = interaction_timestamp()
        cancellation = resolve_cancellation_signal(resolved)
        transport_context = resolve_transport_context(
            interaction_id=interaction_id,
            configuration=resolved,
            cancellation=cancellation,
            timeout=None,
            now=lambda: now,
        )
        endpoint = access.endpoint
        if endpoint is None:
            endpoint = execution_plan.transport_plan.endpoint
        kind = execution_plan.transport.transport_kind
        if kind is None:
            kind = http_transport_kind()
        authorization_context = AuthorizationContext(
            interaction_id,
            resolved.target,
            endpoint,
            kind,
            now,
            execution_plan.transport_plan.body_signing_requirement.acceptable_modes[0],
            cancellation,
        )
        resources = ResponseResources(Bytes(b""), lambda: None)
        frozen = await _authorize_and_freeze(
            candidate_request,
            components,
            execution_plan,
            authorization_context,
            merge_interaction_monitors(candidate_options, candidate_configuration),
        )
        opened = await opener(frozen, transport_context)
        opened_stream = _require_opened_stream(opened)
    except BaseException:
        # The release object does not exist yet. A stream that was already
        # opened still has to be closed, or its worker keeps the socket.
        if opened is not None:
            closer = getattr(opened, "close", None)
            if callable(closer):
                closer()
        if not context.released:
            context.release()
        raise

    release = _Release(opened_stream, context, resources)
    metadata = opened_stream.metadata
    try:
        # A non-success status is a finished HTTP error, not an event stream.
        # Its body is collected under the streaming error limit and mapped
        # before the caller receives an iterator.
        if metadata.outcome.id != _SUCCESS:
            await _raise_service_error(
                opened_stream,
                components,
                metadata,
                resolved.resource_limits.max_streaming_error_body_bytes,
            )
        _require_event_stream(metadata)
    except BaseException:
        release()
        raise

    monitors = merge_interaction_monitors(candidate_options, candidate_configuration)
    completed = MonitoringEvent(
        f"{interaction_id}.completed",
        OpenIdentifier("interaction.completed"),
        interaction_id,
        None,
        now,
        {"status": "completed"},
        {},
    )
    events = _read_events(
        opened_stream,
        mapper,
        metadata,
        resolved.resource_limits.max_frame_bytes,
        resolved.resource_limits.max_response_body_bytes,
        monitors,
        completed,
        release,
    )
    return ServerStream(events, release)


async def _authorize_and_freeze(
    request: ModelRequest,
    components: InteractionExecutionComponents,
    execution_plan: ProtocolExecutionPlan,
    authorization_context: AuthorizationContext,
    monitors: tuple[InteractionMonitor, ...],
) -> TransportRequest:
    """Encode the request, apply authorization, and return the frozen send."""
    # The body is encoded before the handler runs so a signature covers the
    # octets that the stream request will send.
    request_plan = build_protocol_request(request, components, execution_plan)
    body = encode_protocol_payload(components, request_plan)
    transport_plan = execution_plan.transport_plan
    mutable = MutableTransportRequest(
        transport_plan.method,
        _transport_url(transport_plan),
        transport_plan.headers,
        transport_plan.query,
        body,
    )
    redacted = create_pre_authorization_snapshot(mutable, transport_plan.authorization)
    await publish_authorization_will_resolve(
        event_id=f"{authorization_context.interaction_id}.will_resolve",
        interaction_id=authorization_context.interaction_id,
        snapshot=redacted,
        monitors=monitors,
        timestamp=authorization_context.timestamp,
    )
    resolved = resolve_interaction_authorization_handler(
        components,
        transport_plan.authorization,
        transport_plan.body_signing_requirement,
    )
    await read_interaction_credential(
        transport_plan.authorization, authorization_context
    )
    authorized = await apply_authorization_handler(
        resolved,
        transport_plan.authorization,
        authorization_context,
        mutable,
    )
    # Freezing copies the authorized fields. Later streaming reads that copy
    # and cannot observe a mutation of the mutable request.
    return authorized.freeze()


def _transport_url(plan: TransportRequestPlan) -> UriValue:
    """Return the endpoint, appending a non-empty protocol path."""
    # An empty path is the endpoint itself. A relative path is joined without
    # dropping a trailing slash twice or inserting a second slash.
    if plan.path == "":
        return plan.endpoint
    base = plan.endpoint.value
    path = plan.path if plan.path.startswith("/") else f"/{plan.path}"
    if base.endswith("/"):
        base = base[:-1]
    return UriValue(f"{base}{path}", plan.endpoint.is_absolute)


def _event_mapper(
    plan: ProtocolExecutionPlan,
) -> Callable[[bytes, TransportResponseMetadata], tuple[ServerStreamEvent, ...]]:
    """Return the plan's event mapper."""
    mapper = plan.extensions.get(_MAPPER_KEY)
    # The mapper is an opaque plan extension so the runtime does not import a
    # protocol package. A plan that omitted it cannot turn SSE payloads into
    # events, so the interaction fails before the request is sent.
    if not callable(mapper):
        raise _stream_error(
            _UNSUPPORTED,
            _PLANNING,
            _MISSING_MAPPER_CODE,
            _MISSING_MAPPER_MESSAGE,
        )
    return cast(
        Callable[[bytes, TransportResponseMetadata], tuple[ServerStreamEvent, ...]],
        mapper,
    )


def _require_event_stream(metadata: TransportResponseMetadata) -> None:
    """Require the success response to be a server-sent event stream."""
    media_type = metadata.media_type
    # Parameters such as charset do not change the event encoding. Only the
    # type and subtype select SSE.
    if not isinstance(media_type, MediaType):
        raise _stream_error(_PROTOCOL, _FRAMING, _MEDIA_TYPE_CODE, _MEDIA_TYPE_MESSAGE)
    if media_type.type.casefold() != "text" or media_type.subtype.casefold() != (
        "event-stream"
    ):
        raise _stream_error(_PROTOCOL, _FRAMING, _MEDIA_TYPE_CODE, _MEDIA_TYPE_MESSAGE)


async def _raise_service_error(
    opened: _OpenedServerStream,
    components: InteractionExecutionComponents,
    metadata: TransportResponseMetadata,
    max_error_bytes: int,
) -> None:
    """Read a non-success body and raise the mapped service error."""
    body = await _collect_limited(opened, max_error_bytes)
    decoder = resolve_error_outcome_decoder(components, metadata.outcome)
    decoded = decode_response_payload(decoder, Bytes(body))
    # parse_service_error returns the normalized error. Raising it keeps the
    # caller on the same failure path as a unary service error.
    raise parse_service_error(components, decoded, metadata)


async def _collect_limited(opened: _OpenedServerStream, limit: int) -> bytes:
    """Read an async byte stream until it ends or passes ``limit``."""
    chunks: list[bytes] = []
    total = 0
    async for chunk_value in opened:
        # Cast before the check so a transport that yields a non-bytes chunk
        # is rejected even if the protocol annotation says bytes.
        chunk = cast(object, chunk_value)
        if not isinstance(chunk, bytes):
            raise TypeError("stream chunk must be bytes.")
        total += len(chunk)
        # Stop before retaining an error body larger than the streaming limit.
        # The extra octets are not copied into the failure.
        if total > limit:
            raise _stream_error(
                ErrorCategory(OpenIdentifier("network")),
                InteractionPhase(OpenIdentifier("transport")),
                "response_body_too_large",
                "HTTP response body exceeds its byte limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_events(
    opened: _OpenedServerStream,
    mapper: Callable[[bytes, TransportResponseMetadata], tuple[ServerStreamEvent, ...]],
    metadata: TransportResponseMetadata,
    max_frame_bytes: int,
    max_body_bytes: int,
    monitors: tuple[InteractionMonitor, ...],
    completed: MonitoringEvent,
    release: _Release,
) -> AsyncIterator[ServerStreamEvent]:
    """Frame the open body and yield mapped events, then the terminal event."""
    try:
        async for payload in iter_sse_payloads(
            opened,
            max_frame_bytes=max_frame_bytes,
            max_body_bytes=max_body_bytes,
        ):
            # None is the framer's end marker. Completion is published before
            # the terminal event so a caller that stops after that event has
            # already observed the successful end.
            if payload is None:
                break
            produced = cast(object, mapper(payload, metadata))
            if not isinstance(produced, tuple):
                raise TypeError("server stream mapper must return a tuple.")
            # A tuple check does not name the item type, so each item is
            # treated as an arbitrary object before it is accepted as an event.
            for event_value in cast(tuple[object, ...], produced):
                event = event_value
                if not isinstance(event, ServerStreamEvent):
                    raise TypeError(
                        "server stream mapper must return ServerStreamEvent values."
                    )
                yield event
        InteractionTerminalMachine().complete()
        await publish_isolated_monitor_chain(monitors, completed, completed)
        yield ServerStreamEvent.finished()
    finally:
        release()


def _server_stream_opener(
    transport: Transport,
) -> Callable[[TransportRequest, TransportContext], Awaitable[object]]:
    """Return the transport's server-stream opener."""
    opener = cast(object, getattr(transport, "open_server_stream", None))
    # callable accepts any object. A missing attribute stays a planning
    # failure so the request is not authorized for a transport that cannot
    # stream.
    if not callable(opener):
        raise _stream_error(
            _UNSUPPORTED,
            _PLANNING,
            _MISSING_TRANSPORT_CODE,
            _MISSING_TRANSPORT_MESSAGE,
        )
    return cast(
        Callable[[TransportRequest, TransportContext], Awaitable[object]],
        opener,
    )


def _require_opened_stream(opened: object) -> _OpenedServerStream:
    """Require the opener result to expose metadata, chunks, and close."""
    metadata = getattr(opened, "metadata", None)
    closer = getattr(opened, "close", None)
    # The three members are the whole contract the runtime uses. A transport
    # that returns a plain response object cannot be framed as a stream.
    if (
        not isinstance(metadata, TransportResponseMetadata)
        or not callable(closer)
        or not hasattr(opened, "__aiter__")
    ):
        raise TypeError("server stream transport returned an invalid stream.")
    return cast(_OpenedServerStream, opened)


def _stream_error(
    category: ErrorCategory,
    phase: InteractionPhase,
    code: str,
    message: str,
) -> ModelInteractionError:
    """Create one stable server-stream failure without response contents."""
    # Category, phase, and code are the stable contract. The message does not
    # include payloads, endpoints, or credentials.
    return ModelInteractionError(
        category=category,
        phase=phase,
        code=code,
        message=message,
    )
