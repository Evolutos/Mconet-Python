"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import JsonPayload, JsonPayloadEncoder, encode_utf8


def test_json_codec_exports_the_payload_contract_utility_and_encoder() -> None:
    """Verify JSON decoding stays out of the public JSON module."""
    # The payload port, UTF-8 utility, and payload encoder are available.
    # Decoders, the media-type matcher, and component metadata remain later work.
    assert mconet.codec.json.__all__ == (
        "JsonPayload",
        "JsonPayloadEncoder",
        "encode_utf8",
    )
    assert mconet.codec.json.JsonPayload is JsonPayload
    assert mconet.codec.json.JsonPayloadEncoder is JsonPayloadEncoder
    assert mconet.codec.json.encode_utf8 is encode_utf8
