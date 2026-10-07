"""Structural and responsibility tests for the payload encoder contract."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import get_type_hints

from mconet.core.domain import Bytes, MediaType, OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    PayloadEncoder,
    TransportBody,
)


class _Encoder:
    """Ordinary configurable encoder implementation used by contract tests."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        body: TransportBody,
    ) -> None:
        """Store exact component metadata and the configured encoded body."""
        # Recording calls makes payload identity observable while the prebuilt
        # body keeps these tests independent from any concrete wire format.
        self.descriptor = descriptor
        self.body = body
        self.calls: list[ErasedRuntimeValue] = []

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record one native payload and return the configured transport body."""
        # A contract stub performs no task interpretation, authorization, request
        # mutation, or I/O; concrete codecs alone decide how bytes are produced.
        self.calls.append(payload)
        return self.body


@dataclass(frozen=True, slots=True)
class _IncompleteEncoder:
    """Component-shaped fixture intentionally missing payload encoding."""

    descriptor: ComponentDescriptor
    """Valid metadata isolates absence of the required behavior method."""


def _body(content: bytes = b'{"message":"hello"}') -> TransportBody:
    """Build one immutable JSON transport body for encoder contract tests."""
    # Explicit Bytes and MediaType values exercise the current complete-body
    # representation without embedding a JSON encoder implementation in tests.
    return TransportBody(Bytes(content), MediaType("application", "json"))


def _accept_encoder(encoder: PayloadEncoder) -> PayloadEncoder:
    """Return an encoder after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary implementation's metadata and encode method
    # without an SDK base class, explicit registration, or a generic adapter.
    return encoder


def test_payload_encoder_accepts_ordinary_structural_class() -> None:
    """Require only component metadata and the documented encode operation."""
    encoder = _Encoder(
        ComponentDescriptor("Fixture encoder", "1.0.0", "application"),
        _body(),
    )

    accepted = _accept_encoder(encoder)

    # Static and runtime conformance agree without inheritance, lifecycle hooks,
    # a component ID, or one concrete serialization library in the SPI.
    assert accepted is encoder
    assert isinstance(encoder, PayloadEncoder)
    assert encoder.descriptor.name == "Fixture encoder"


def test_payload_encoder_preserves_payload_and_body_identity() -> None:
    """Pass the exact native payload through and return the exact encoded body."""
    native_payload = {"message": "hello"}
    payload = ErasedRuntimeValue(
        OpenIdentifier("protocol.request"),
        native_payload,
        "request.v1",
    )
    body = _body()
    encoder = _Encoder(
        ComponentDescriptor("Fixture encoder", "1.0.0", "application"),
        body,
    )

    result = encoder.encode(payload)

    # Identity proves Core supplies the selected native value unchanged and the
    # protocol does not rebuild, authorize, or wrap the encoder-produced body.
    assert encoder.calls == [payload]
    assert encoder.calls[0] is payload
    assert payload.value is native_payload
    assert result is body
    assert result.bytes == b'{"message":"hello"}'
    assert result.media_type is body.media_type


def test_payload_encoder_allows_an_explicit_empty_body() -> None:
    """Preserve zero encoded bytes as a present complete transport body."""
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.empty"), None)
    body = _body(b"")
    encoder = _Encoder(
        ComponentDescriptor("Fixture encoder", "1.0.0", "application"),
        body,
    )

    result = encoder.encode(payload)

    # Zero length is a valid encoding result, not an absent body, a streaming
    # placeholder, or permission for the protocol wrapper to invent bytes.
    assert result is body
    assert result.bytes == b""
    assert len(result.bytes) == 0


def test_payload_encoder_has_exact_synchronous_method_surface() -> None:
    """Lock the method name, argument order, and synchronous encoding semantics."""
    method = PayloadEncoder.encode
    annotations = get_type_hints(method)

    # The narrow signature prevents model requests, access, credentials,
    # authorization windows, mutable requests, and transports from leaking in.
    assert tuple(inspect.signature(method).parameters) == ("self", "payload")
    assert annotations == {
        "payload": ErasedRuntimeValue,
        "return": TransportBody,
    }
    assert not inspect.iscoroutinefunction(method)


def test_payload_encoder_requires_complete_behavior_surface() -> None:
    """Reject component metadata when the encode operation is absent."""
    incomplete = _IncompleteEncoder(
        ComponentDescriptor("Incomplete", "1.0.0", "application")
    )

    # Descriptor conformance alone cannot make a component usable as an encoder;
    # runtime structural recognition also requires the exact behavior member.
    assert not isinstance(incomplete, PayloadEncoder)


def test_payload_encoder_excludes_other_pipeline_responsibilities() -> None:
    """Keep task mapping, authorization, transport, and decoding out of the SPI."""
    encoder = _Encoder(
        ComponentDescriptor("Fixture encoder", "1.0.0", "application"),
        _body(),
    )

    # The protocol exposes one encode operation only. Negative checks prevent an
    # implementation contract from absorbing adjacent runtime pipeline stages.
    for forbidden_member in (
        "map_request",
        "prepare_plan",
        "authorize",
        "mutate_request",
        "send",
        "decode",
        "register",
    ):
        assert not hasattr(encoder, forbidden_member)
