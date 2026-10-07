"""Structural and responsibility tests for the payload decoder contract."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import get_type_hints

from mconet.core.domain import Bytes, OpenIdentifier
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue, PayloadDecoder


class _Decoder:
    """Ordinary configurable decoder implementation used by contract tests."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        payload: ErasedRuntimeValue,
    ) -> None:
        """Store exact component metadata and the configured decoded payload."""
        # Recording calls makes byte identity observable while the prebuilt
        # payload keeps these tests independent from one concrete wire format.
        self.descriptor = descriptor
        self.payload = payload
        self.calls: list[Bytes] = []

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record complete response bytes and return the configured payload."""
        # A contract stub performs no transport, component selection, task
        # parsing, or output assembly; concrete codecs alone parse the bytes.
        self.calls.append(raw_data)
        return self.payload


@dataclass(frozen=True, slots=True)
class _IncompleteDecoder:
    """Component-shaped fixture intentionally missing payload decoding."""

    descriptor: ComponentDescriptor
    """Valid metadata isolates absence of the required behavior method."""


def _accept_decoder(decoder: PayloadDecoder) -> PayloadDecoder:
    """Return a decoder after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary implementation's metadata and decode method
    # without an SDK base class, explicit registration, or a generic adapter.
    return decoder


def test_payload_decoder_accepts_ordinary_structural_class() -> None:
    """Require only component metadata and the documented decode operation."""
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.response"), {})
    decoder = _Decoder(
        ComponentDescriptor("Fixture decoder", "1.0.0", "application"),
        payload,
    )

    accepted = _accept_decoder(decoder)

    # Static and runtime conformance agree without inheritance, lifecycle hooks,
    # a component ID, or one concrete parsing library in the public SPI.
    assert accepted is decoder
    assert isinstance(decoder, PayloadDecoder)
    assert decoder.descriptor.name == "Fixture decoder"


def test_payload_decoder_preserves_bytes_and_payload_identity() -> None:
    """Pass exact response bytes through and return the exact native payload."""
    raw_data = Bytes(bytes((0, 127, 255)))
    native_payload = {"status": "completed"}
    payload = ErasedRuntimeValue(
        OpenIdentifier("protocol.response"),
        native_payload,
        "response.v1",
    )
    decoder = _Decoder(
        ComponentDescriptor("Fixture decoder", "1.0.0", "application"),
        payload,
    )

    result = decoder.decode(raw_data)

    # Identity proves Core supplies the complete transport bytes unchanged and
    # does not rebuild or interpret the decoder's protocol-native output.
    assert decoder.calls == [raw_data]
    assert decoder.calls[0] is raw_data
    assert result is payload
    assert result.value is native_payload
    assert result.type_id == OpenIdentifier("protocol.response")


def test_payload_decoder_allows_explicit_empty_bytes() -> None:
    """Pass zero response bytes to the selected decoder without inventing data."""
    raw_data = Bytes(b"")
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.empty"), None)
    decoder = _Decoder(
        ComponentDescriptor("Fixture decoder", "1.0.0", "application"),
        payload,
    )

    result = decoder.decode(raw_data)

    # Empty bytes remain a present complete input. The selected decoder decides
    # whether that representation is valid for its protocol and schema.
    assert decoder.calls[0] is raw_data
    assert len(decoder.calls[0]) == 0
    assert result is payload


def test_payload_decoder_has_exact_synchronous_method_surface() -> None:
    """Lock the method name, argument order, and synchronous decoding semantics."""
    method = PayloadDecoder.decode
    annotations = get_type_hints(method)

    # Content type and transport metadata are intentionally absent: Core fixes
    # one compatible decoder before sending and only validates metadata later.
    assert tuple(inspect.signature(method).parameters) == ("self", "raw_data")
    assert annotations == {
        "raw_data": Bytes,
        "return": ErasedRuntimeValue,
    }
    assert not inspect.iscoroutinefunction(method)


def test_payload_decoder_requires_complete_behavior_surface() -> None:
    """Reject component metadata when the decode operation is absent."""
    incomplete = _IncompleteDecoder(
        ComponentDescriptor("Incomplete", "1.0.0", "application")
    )

    # Descriptor conformance alone cannot make a component usable as a decoder;
    # runtime structural recognition also requires the exact behavior member.
    assert not isinstance(incomplete, PayloadDecoder)


def test_payload_decoder_excludes_other_pipeline_responsibilities() -> None:
    """Keep transport, selection, task parsing, and output assembly out of the SPI."""
    decoder = _Decoder(
        ComponentDescriptor("Fixture decoder", "1.0.0", "application"),
        ErasedRuntimeValue(OpenIdentifier("protocol.response"), None),
    )

    # The protocol exposes one decode operation only. Negative checks prevent it
    # from absorbing adjacent response-pipeline or component-resolution stages.
    for forbidden_member in (
        "send",
        "select_decoder",
        "replace_for_content_type",
        "parse_response",
        "map_response",
        "assemble_output",
        "authorize",
        "register",
    ):
        assert not hasattr(decoder, forbidden_member)
