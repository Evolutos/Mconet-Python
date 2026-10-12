"""Tests for the client-api module boundary."""

import mconet.client
from mconet.client.model_client import ModelClient


def test_client_api_exports_the_reusable_client() -> None:
    """Verify the client package exports the unified ModelClient."""
    assert mconet.client.__all__ == ("ModelClient",)
    assert mconet.client.ModelClient is ModelClient
