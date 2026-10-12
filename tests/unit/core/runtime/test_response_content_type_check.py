"""Tests that Content-Type checks do not reselect a decoder."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import (
    Bytes,
    CompatibilityPolicy,
    Headers,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._response_content_type_check import (
    check_response_content_type,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    ErasedRuntimeValue,
    TransportOutcome,
    TransportResponseMetadata,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


class _Decoder:
    """Decoder whose contract declares one input media type."""

    def __init__(self, media_type: MediaType) -> None:
        """Store a contract that accepts one wire media type."""
        self.descriptor = ComponentDescriptor(
            "decoder",
            "1.0.0",
            "application",
            ComponentTypeContract(
                inputs=(
                    ComponentTypePort(
                        "body",
                        OpenIdentifier("transport.bytes"),
                        None,
                        media_type,
                    ),
                )
            ),
        )
        self.decode_calls = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record a decode that the content-type check must not perform."""
        del raw_data
        self.decode_calls += 1
        return ErasedRuntimeValue(OpenIdentifier("json.value"), None)


def _metadata(media_type: MediaType) -> TransportResponseMetadata:
    """Return response metadata with one actual media type."""
    return TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("success")),
        Headers(),
        media_type=media_type,
    )


def test_content_type_check_keeps_the_same_decoder() -> None:
    """Verify a match keeps the decoder and a mismatch does not replace it."""
    json_type = MediaType("application", "json")
    decoder = _Decoder(json_type)
    alternate = _Decoder(MediaType("text", "plain"))
    checked, diagnostics = check_response_content_type(
        _metadata(json_type),
        DecoderSelection(json_type),
        decoder,
        CompatibilityPolicy(OpenIdentifier("strict")),
    )
    mismatch = _capture(
        lambda: check_response_content_type(
            _metadata(MediaType("text", "plain")),
            DecoderSelection(json_type),
            decoder,
            CompatibilityPolicy(OpenIdentifier("strict")),
        )
    )

    assert checked is decoder
    assert checked is not alternate
    assert diagnostics == ()
    assert decoder.decode_calls == 0
    assert alternate.decode_calls == 0
    assert isinstance(mismatch, ModelInteractionError)
    assert mismatch.code == "response_media_type_mismatch"
