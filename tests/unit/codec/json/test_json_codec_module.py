"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import (
    JsonPayload,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
    collect_bounded_bytes,
    encode_utf8,
)


def test_json_codec_exports_success_decoding_without_error_decoding() -> None:
    """Verify error decoding stays out of the public JSON module."""
    # Success decoding is available. The error decoder, media-type matcher, and
    # component type contracts remain later work.
    assert mconet.codec.json.__all__ == (
        "JsonPayload",
        "JsonPayloadEncoder",
        "JsonSuccessPayloadDecoder",
        "collect_bounded_bytes",
        "encode_utf8",
    )
    assert mconet.codec.json.JsonPayload is JsonPayload
    assert mconet.codec.json.JsonPayloadEncoder is JsonPayloadEncoder
    assert mconet.codec.json.JsonSuccessPayloadDecoder is JsonSuccessPayloadDecoder
    assert mconet.codec.json.collect_bounded_bytes is collect_bounded_bytes
    assert mconet.codec.json.encode_utf8 is encode_utf8
