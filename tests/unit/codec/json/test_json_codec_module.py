"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import (
    JsonPayload,
    JsonPayloadEncoder,
    collect_bounded_bytes,
    encode_utf8,
)


def test_json_codec_exports_payload_encoding_and_bounded_collection() -> None:
    """Verify JSON decoding stays out of the public JSON module."""
    # Collection stops an oversized body before a decoder parses it. Decoders,
    # the media-type matcher, and component metadata remain later work.
    assert mconet.codec.json.__all__ == (
        "JsonPayload",
        "JsonPayloadEncoder",
        "collect_bounded_bytes",
        "encode_utf8",
    )
    assert mconet.codec.json.JsonPayload is JsonPayload
    assert mconet.codec.json.JsonPayloadEncoder is JsonPayloadEncoder
    assert mconet.codec.json.collect_bounded_bytes is collect_bounded_bytes
    assert mconet.codec.json.encode_utf8 is encode_utf8
