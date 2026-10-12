"""Tests that payload decoding failures share one stable error."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    Bytes,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._payload_decoding import decode_response_payload
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue

_BODY = b'{"secret":"mconet-test-bearer-token-not-secret"}'


class _Decoder:
    """Decoder that returns or raises a prepared result."""

    def __init__(self, result: object) -> None:
        """Store the value or error produced by ``decode``."""
        self.descriptor = ComponentDescriptor("decoder", "1.0.0", "application")
        self.result = result
        self.calls = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record one decode and return or raise the prepared result."""
        del raw_data
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return cast(ErasedRuntimeValue, self.result)


def test_decode_returns_the_value_or_one_normalized_error() -> None:
    """Verify one success and one unknown failure stay distinct."""
    payload = ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": True})
    success = _Decoder(payload)
    decoded = decode_response_payload(success, Bytes(_BODY))
    failure = _Decoder(RuntimeError(_BODY.decode("utf-8")))
    try:
        decode_response_payload(failure, Bytes(_BODY))
    except ModelInteractionError as error:
        normalized = error
    else:
        raise AssertionError("Expected decoding to fail.")

    assert decoded is payload
    assert success.calls == 1
    assert failure.calls == 1
    assert normalized.code == "payload_decoding_failed"
    assert normalized.phase.id.value == "decoding"
    assert "mconet-test-bearer-token-not-secret" not in normalized.message
    assert isinstance(normalized.cause, RuntimeError)


def test_decoder_model_error_is_not_replaced() -> None:
    """Verify a decoder's own interaction error is preserved."""
    original = ModelInteractionError(
        ErrorCategory(OpenIdentifier("protocol")),
        InteractionPhase(OpenIdentifier("decoding")),
        "invalid_json",
        "The JSON document is not valid.",
    )
    decoder = _Decoder(original)
    try:
        decode_response_payload(decoder, Bytes(b"{}"))
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected decoding to fail.")

    assert raised is original
    assert decoder.calls == 1
