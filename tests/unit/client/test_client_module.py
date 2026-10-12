"""Tests for the client-api module boundary."""

import mconet.client
from mconet.client.conversation_request_builder import ConversationRequestBuilder
from mconet.client.model_client import ModelClient
from mconet.client.text_request import model_request_from_text


def test_client_api_exports_the_reusable_client() -> None:
    """Verify the client package exports the client, builder, and text conversion."""
    assert mconet.client.__all__ == (
        "ConversationRequestBuilder",
        "ModelClient",
        "model_request_from_text",
    )
    assert mconet.client.ModelClient is ModelClient
    assert mconet.client.ConversationRequestBuilder is ConversationRequestBuilder
    assert mconet.client.model_request_from_text is model_request_from_text
