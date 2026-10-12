"""Public client API and default composition root for Mconet."""

from mconet.client.conversation_request_builder import ConversationRequestBuilder
from mconet.client.model_client import ModelClient
from mconet.client.text_request import model_request_from_text


def make_default() -> ModelClient:
    """Return a client that injects no application components.

    Unset encoder, decoder, transport, and authorization roles use the JSON
    codec, the system HTTP transport, and the basic authorization handlers.
    Those objects are SDK-owned. ``close`` releases them. The returned
    configuration does not list them as injected components.

    Returns:
        A client that is accepting requests and owns the builtin components.
    """
    return ModelClient.make_default()

__all__ = (
    "ConversationRequestBuilder",
    "ModelClient",
    "make_default",
    "model_request_from_text",
)
