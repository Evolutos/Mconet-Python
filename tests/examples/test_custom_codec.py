"""Custom codecs can replace the encoder and each decoder separately."""

from __future__ import annotations

import asyncio

from examples.custom_codec import run_custom_codecs


def test_encoder_and_decoders_are_replaced_separately() -> None:
    """Verify the success path uses the encoder and success decoder only."""
    encoder_calls, success_calls, error_calls, replacement_calls = asyncio.run(
        run_custom_codecs()
    )
    assert encoder_calls == 2
    assert success_calls == 1
    assert error_calls == 0
    assert replacement_calls == 1
