"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import JsonPayload, encode_utf8


def test_json_codec_exports_the_payload_contract_and_utf8_utility() -> None:
    """Verify JSON encoding and decoding stay out of the public JSON module."""
    # The payload port and UTF-8 utility are available. The JSON payload
    # encoder, decoders, matcher, and component metadata remain later work.
    assert mconet.codec.json.__all__ == ("JsonPayload", "encode_utf8")
    assert mconet.codec.json.JsonPayload is JsonPayload
    assert mconet.codec.json.encode_utf8 is encode_utf8
