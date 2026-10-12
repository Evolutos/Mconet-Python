"""Public client API and default composition root for Mconet."""

from mconet.client.conversation_request_builder import ConversationRequestBuilder
from mconet.client.model_client import ModelClient
from mconet.client.text_request import model_request_from_text
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.service_access import ServiceAccess


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


def make_openai_compatible(
    target: ModelTarget,
    service_access: ServiceAccess,
    *,
    max_response_body_bytes: int = 16_777_216,
) -> ModelClient:
    """Return a client whose defaults are one OpenAI-compatible binding.

    Args:
        target: Default model target stored on the client.
        service_access: Default access stored on the client.
        max_response_body_bytes: Body limit passed to the binding's decoders.

    Returns:
        The client produced by :meth:`ModelClient.make_openai_compatible`.
    """
    return ModelClient.make_openai_compatible(
        target,
        service_access,
        max_response_body_bytes=max_response_body_bytes,
    )


__all__ = (
    "ConversationRequestBuilder",
    "ModelClient",
    "make_default",
    "make_openai_compatible",
    "model_request_from_text",
)
