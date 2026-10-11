"""Tests for the integration-openai-compatible module boundary."""

import mconet.integration.openai_compatible
from mconet.integration.openai_compatible import OpenAIChatMessageDTO


def test_openai_compatible_exports_the_defined_protocol_values() -> None:
    """Verify the module publishes exactly the protocol values defined so far."""
    assert mconet.integration.openai_compatible.__all__ == ("OpenAIChatMessageDTO",)
    assert mconet.integration.openai_compatible.OpenAIChatMessageDTO is (
        OpenAIChatMessageDTO
    )
