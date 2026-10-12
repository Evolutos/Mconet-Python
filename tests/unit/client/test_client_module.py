"""Tests for the client-api module boundary."""

import mconet.client
from mconet.client.conversation_request_builder import ConversationRequestBuilder
from mconet.client.model_client import ModelClient


def test_client_api_exports_the_reusable_client() -> None:
    """Verify the client package exports the client and conversation builder."""
    assert mconet.client.__all__ == (
        "ConversationRequestBuilder",
        "ModelClient",
    )
    assert mconet.client.ModelClient is ModelClient
    assert mconet.client.ConversationRequestBuilder is ConversationRequestBuilder
