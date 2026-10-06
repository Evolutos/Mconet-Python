"""Tests for the client-api module boundary."""

import mconet.client


def test_client_api_imports_without_public_behavior() -> None:
    """Verify the empty client module has no premature public API."""
    assert mconet.client.__all__ == ()
