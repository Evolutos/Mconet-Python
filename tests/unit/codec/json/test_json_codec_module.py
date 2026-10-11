"""Tests for the codec-json module boundary."""

import mconet.codec.json
from mconet.codec.json import JsonPayload


def test_json_codec_exports_only_the_frozen_payload_contract() -> None:
    """Verify encoding and decoding stay out of the public JSON module."""
    # S7.1 freezes the payload port only. Encoder, decoder, matcher, and
    # component metadata belong to later work packages and must not appear here.
    assert mconet.codec.json.__all__ == ("JsonPayload",)
    assert mconet.codec.json.JsonPayload is JsonPayload
