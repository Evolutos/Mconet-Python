"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayload,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
    collect_bounded_bytes,
    encode_utf8,
)


def test_json_codec_exports_payload_codecs_without_component_metadata() -> None:
    """Verify media-type matching and type contracts stay out of the module."""
    # Encoding, bounded collection, and both decoders are available. The
    # media-type matcher and component type contracts remain later work.
    assert mconet.codec.json.__all__ == (
        "JsonErrorPayloadDecoder",
        "JsonPayload",
        "JsonPayloadEncoder",
        "JsonSuccessPayloadDecoder",
        "collect_bounded_bytes",
        "encode_utf8",
    )
    assert mconet.codec.json.JsonErrorPayloadDecoder is JsonErrorPayloadDecoder
    assert mconet.codec.json.JsonPayload is JsonPayload
    assert mconet.codec.json.JsonPayloadEncoder is JsonPayloadEncoder
    assert mconet.codec.json.JsonSuccessPayloadDecoder is JsonSuccessPayloadDecoder
    assert mconet.codec.json.collect_bounded_bytes is collect_bounded_bytes
    assert mconet.codec.json.encode_utf8 is encode_utf8
