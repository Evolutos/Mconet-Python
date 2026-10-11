"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
    JsonErrorPayloadDecoder,
    JsonPayload,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
    collect_bounded_bytes,
    encode_utf8,
    is_json_media_type,
)


def test_json_codec_exports_payload_codecs_and_encoder_metadata() -> None:
    """Verify the public JSON module includes the encoder type contract."""
    # Encoding, decoding, collection, and media-type matching stay available.
    # Decoder contracts and capabilities remain later work.
    assert mconet.codec.json.__all__ == (
        "JSON_PAYLOAD_ENCODER_DESCRIPTOR",
        "JSON_PAYLOAD_ENCODER_TYPE_CONTRACT",
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
    assert (
        mconet.codec.json.JSON_PAYLOAD_ENCODER_TYPE_CONTRACT
        is JSON_PAYLOAD_ENCODER_TYPE_CONTRACT
    )
    assert mconet.codec.json.JsonPayloadEncoder is JsonPayloadEncoder
    assert mconet.codec.json.JsonSuccessPayloadDecoder is JsonSuccessPayloadDecoder
    assert mconet.codec.json.collect_bounded_bytes is collect_bounded_bytes
    assert mconet.codec.json.encode_utf8 is encode_utf8
    assert mconet.codec.json.is_json_media_type is is_json_media_type
