"""Tests for the S0 client-api module boundary."""

import mconet.client


def test_client_api_imports_without_public_behavior() -> None:
    """Verify the empty client module has no premature public API."""
    # ModelClient and default factories belong to S12; S0 establishes only the
    # package boundary that later becomes the unique default composition root.
    assert mconet.client.__all__ == ()
