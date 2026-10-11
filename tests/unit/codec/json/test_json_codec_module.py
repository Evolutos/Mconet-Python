"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
    JsonErrorPayloadDecoder,
    JsonPayload,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
    collect_bounded_bytes,
    encode_utf8,
    is_json_media_type,
)


def test_json_codec_exports_payload_codecs_without_component_contracts() -> None:
    """Verify component type contracts stay out of the public JSON module."""
    # Encoding, decoding, collection, and media-type matching are available.
    # Component type contracts and capabilities remain later work.
    assert mconet.codec.json.__all__ == (
        "JSON_PAYLOAD_ENCODER_DESCRIPTOR",
        "JsonErrorPayloadDecoder",
        "JsonPayload",
        "JsonPayloadEncoder",
        "JsonSuccessPayloadDecoder",
        "collect_bounded_bytes",
        "encode_utf8",
        "is_json_media_type",
    )
    assert mconet.codec.json.JsonErrorPayloadDecoder is JsonErrorPayloadDecoder
    assert mconet.codec.json.JsonPayload is JsonPayload
    assert (
        mconet.codec.json.JSON_PAYLOAD_ENCODER_DESCRIPTOR
        is JSON_PAYLOAD_ENCODER_DESCRIPTOR
    )
    assert mconet.codec.json.JsonPayloadEncoder is JsonPayloadEncoder
    assert mconet.codec.json.JsonSuccessPayloadDecoder is JsonSuccessPayloadDecoder
    assert mconet.codec.json.collect_bounded_bytes is collect_bounded_bytes
    assert mconet.codec.json.encode_utf8 is encode_utf8
    assert mconet.codec.json.is_json_media_type is is_json_media_type
