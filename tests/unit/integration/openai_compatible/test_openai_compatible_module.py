"""Tests for the S0 integration-openai-compatible module boundary."""

import mconet.integration.openai_compatible


def test_openai_compatible_imports_without_public_behavior() -> None:
    """Verify the empty integration module has no premature protocol API."""
    # Protocol DTOs and mapping belong to S10; S0 establishes only the package
    # boundary that later owns those private implementation details.
    assert mconet.integration.openai_compatible.__all__ == ()
