"""Structural and responsibility tests for the asynchronous transport contract."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import get_type_hints

from mconet.core.domain import (
    Bytes,
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


class _Transport:
    """Ordinary configurable asynchronous transport used by contract tests."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        response: TransportResponse,
    ) -> None:
        """Store exact component metadata and the configured wire response."""
        # An ordered call record exposes input identities while the prebuilt
        # response keeps this protocol test independent from a network stack.
        self.descriptor = descriptor
        self.response = response
        self.calls: list[tuple[TransportRequest, TransportContext]] = []

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record one dispatch tuple and return the configured response."""
        # Yield once to exercise a genuine awaitable boundary without performing
        # network I/O, mutating the frozen request, or interpreting credentials.
        await asyncio.sleep(0)
        self.calls.append((request, context))
        return self.response


class _TransportFailure(RuntimeError):
    """Represent one exact native transport failure in contract tests."""


class _FailingTransport:
    """Ordinary transport that propagates one configured asynchronous failure."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        failure: _TransportFailure,
    ) -> None:
        """Store component metadata and the exact failure to raise."""
        # Keeping the exception object makes identity observable and confirms the
        # protocol wrapper does not normalize errors before Runtime receives them.
        self.descriptor = descriptor
        self.failure = failure

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Raise the configured failure after accepting complete dispatch inputs."""
        # Inputs are intentionally observed only to preserve the complete method
        # contract; an implementation failure produces no partial response.
        del request, context
        raise self.failure


@dataclass(frozen=True, slots=True)
class _IncompleteTransport:
    """Component-shaped fixture intentionally missing asynchronous sending."""

    descriptor: ComponentDescriptor
    """Valid metadata isolates absence of the required behavior method."""


def _request() -> TransportRequest:
    """Build one fully encoded and frozen request for dispatch tests."""
    # Public immutable values model the exact object a completed authorization
    # window passes to Transport without exposing authorization configuration.
    return TransportRequest(
        "POST",
        UriValue("https://models.example.test/v1/run", True),
        Headers(),
        QueryParameters(),
        TransportBody(Bytes(b'{"input":"hello"}'), MediaType("application", "json")),
    )


def _context() -> TransportContext:
    """Build one complete per-interaction transport context."""
    # Finite limits are already resolved before dispatch; the transport receives
    # no configuration layers, defaulting logic, or unbounded sentinels.
    limits = ResolvedInteractionResourceLimits(4_096, 1_024, 512)
    return TransportContext("interaction-1", limits)


def _response() -> TransportResponse:
    """Build one normalized successful response with complete bytes."""
    # The fixture supplies normalized outcome and native body independently so
    # Transport never needs to decode or interpret service payload semantics.
    metadata = TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("success")),
        Headers(),
        status_code=200,
    )
    return TransportResponse(metadata, Bytes(b'{"status":"completed"}'))


def _accept_transport(transport: Transport) -> Transport:
    """Return a transport after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary implementation's metadata and async method
    # without an SDK base class, explicit registration, or a network wrapper.
    return transport


def test_transport_accepts_ordinary_structural_class() -> None:
    """Require only component metadata and the documented asynchronous send."""
    transport = _Transport(
        ComponentDescriptor("Fixture transport", "1.0.0", "application"),
        _response(),
    )

    accepted = _accept_transport(transport)

    # Static and runtime conformance agree without inheritance, lifecycle hooks,
    # a component ID, or one concrete networking library in the public SPI.
    assert accepted is transport
    assert isinstance(transport, Transport)
    assert transport.descriptor.name == "Fixture transport"


def test_transport_preserves_dispatch_inputs_and_response_identity() -> None:
    """Pass exact dispatch values through and return the exact wire response."""
    request = _request()
    context = _context()
    response = _response()
    transport = _Transport(
        ComponentDescriptor("Fixture transport", "1.0.0", "application"),
        response,
    )

    result = asyncio.run(transport.send(request, context))

    # Exact identities prove the transport observes the frozen request/context
    # and returns its protocol-neutral result without rebuilding pipeline values.
    assert transport.calls == [(request, context)]
    assert transport.calls[0][0] is request
    assert transport.calls[0][1] is context
    assert result is response
    assert result.body == b'{"status":"completed"}'


def test_transport_propagates_asynchronous_failure_without_partial_response() -> None:
    """Preserve the exact failure raised by an ordinary transport implementation."""
    failure = _TransportFailure("connection failed")
    transport = _FailingTransport(
        ComponentDescriptor("Failing transport", "1.0.0", "application"),
        failure,
    )

    try:
        asyncio.run(transport.send(_request(), _context()))
    except _TransportFailure as error:
        # Identity proves this abstract layer neither wraps the native failure nor
        # invents a response value after the asynchronous operation fails.
        assert error is failure
    else:
        raise AssertionError("Expected transport failure to be raised.")


def test_transport_has_exact_asynchronous_method_surface() -> None:
    """Lock the method name, argument order, types, and asynchronous semantics."""
    method = Transport.send
    annotations = get_type_hints(method)

    # Only frozen protocol-neutral dispatch values cross this boundary; model,
    # message, adapter, decoder, authorization, and credential types are absent.
    assert tuple(inspect.signature(method).parameters) == (
        "self",
        "request",
        "context",
    )
    assert annotations == {
        "request": TransportRequest,
        "context": TransportContext,
        "return": TransportResponse,
    }
    assert inspect.iscoroutinefunction(method)


def test_transport_requires_complete_behavior_surface() -> None:
    """Reject component metadata when asynchronous sending is absent."""
    incomplete = _IncompleteTransport(
        ComponentDescriptor("Incomplete", "1.0.0", "application")
    )

    # Descriptor conformance alone cannot make a component usable as transport;
    # runtime structural recognition also requires the send behavior member.
    assert not isinstance(incomplete, Transport)


def test_transport_excludes_other_pipeline_responsibilities() -> None:
    """Keep mapping, codec, authorization, and output assembly out of the SPI."""
    transport = _Transport(
        ComponentDescriptor("Fixture transport", "1.0.0", "application"),
        _response(),
    )

    # The protocol exposes one send operation only. Negative checks prevent it
    # from absorbing adjacent runtime stages or credential ownership.
    for forbidden_member in (
        "map_request",
        "prepare_plan",
        "encode",
        "decode",
        "authorize",
        "read_credential",
        "assemble_output",
        "register",
    ):
        assert not hasattr(transport, forbidden_member)
