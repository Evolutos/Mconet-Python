"""Tests for the S0 codec-json module boundary."""

import mconet.codec.json


def test_json_codec_imports_without_public_behavior() -> None:
    """Verify the empty JSON codec builds without premature behavior."""
    # Encoder and decoder behavior belongs to S7; S0 establishes only the
    # independently buildable package boundary used by those work packages.
    assert mconet.codec.json.__all__ == ()
