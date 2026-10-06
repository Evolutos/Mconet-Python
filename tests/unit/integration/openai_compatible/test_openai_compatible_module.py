"""Tests for the integration-openai-compatible module boundary."""

import mconet.integration.openai_compatible


def test_openai_compatible_imports_without_public_behavior() -> None:
    """Verify the empty integration module has no premature protocol API."""
    assert mconet.integration.openai_compatible.__all__ == ()
