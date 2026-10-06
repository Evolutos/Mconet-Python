"""Tests for the codec-json module boundary."""

import mconet.codec.json


def test_json_codec_imports_without_public_behavior() -> None:
    """Verify the empty JSON codec builds without premature behavior."""
    assert mconet.codec.json.__all__ == ()
