"""Default binding of the OpenAI-compatible chat completions integration."""

from __future__ import annotations

from typing import cast

from mconet.auth.basic import (
    ApiKeyHeaderAuthorizationHandler,
    BearerAuthorizationHandler,
    NoAuthorizationHandler,
)
from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import (
    CompatibilityPolicy,
    InteractionMode,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.runtime._integration_type_key import IntegrationTypeKey
from mconet.core.runtime._model_integration_binding import ModelIntegrationBinding
from mconet.core.spi import ModelTargetMatch, TaskMatch
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)
from mconet.transport.http_system import DefaultSystemHttpTransport

OPENAI_COMPATIBLE_BINDING_ID = "openai-compatible.chat-completions"
"""Diagnostic label of the default binding."""

OPENAI_COMPATIBLE_BINDING_VERSION = "1.0.0"
"""Version of the default binding's component combination."""

_CONVERSATION_TASK_TYPE = OpenIdentifier("conversation.generate")
_UNARY_MODE_ID = OpenIdentifier("unary")
_SERVER_STREAM_MODE_ID = OpenIdentifier("server_stream")
_ACCEPTED_MODE_IDS = frozenset((_UNARY_MODE_ID, _SERVER_STREAM_MODE_ID))

OPENAI_COMPATIBLE_TYPE_KEY = IntegrationTypeKey(
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID, _CONVERSATION_TASK_TYPE, _UNARY_MODE_ID
)
"""Exact type table key for the unary chat completions binding."""

OPENAI_COMPATIBLE_SERVER_STREAM_TYPE_KEY = IntegrationTypeKey(
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    _CONVERSATION_TASK_TYPE,
    _SERVER_STREAM_MODE_ID,
)
"""Exact type table key for the server-stream chat completions binding."""

# Specificity scores only describe the match in the plan snapshot; the type
# table decides by exact key, so their values never rank candidates.
_PROTOCOL_SPECIFICITY = 1
_TASK_SPECIFICITY = 1


class _ProtocolTargetMatcher:
    """Accept every target that names the chat completions protocol.

    Service, model, and deployment are not consulted, because any service and
    model may speak the protocol.
    """

    __slots__ = ()

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Return a match only for the chat completions protocol."""
        if target.protocol_id != OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID:
            return None
        return ModelTargetMatch(True, _PROTOCOL_SPECIFICITY)


class _ConversationUnaryMatcher:
    """Accept conversation generation in unary or server-stream mode."""

    __slots__ = ()

    def match(self, task: TaskDescriptor, mode: InteractionMode) -> TaskMatch | None:
        """Return a match for ``conversation.generate`` in an accepted mode."""
        # One binding serves both modes. The type table still keeps a separate
        # key for each mode so lookup stays exact.
        if task.type != _CONVERSATION_TASK_TYPE or mode.id not in _ACCEPTED_MODE_IDS:
            return None
        return TaskMatch(True, _TASK_SPECIFICITY)


def openai_compatible_binding(
    *,
    max_response_body_bytes: int,
    compatibility_policy: CompatibilityPolicy | None = None,
    transport: DefaultSystemHttpTransport | None = None,
) -> ModelIntegrationBinding:
    """Return the explicit component combination for chat completions.

    The binding fixes one instance per role, with nothing looked up by id:

    * the chat completions adapter for the given compatibility policy;
    * the JSON payload encoder, and JSON success and error decoders that
      share one response body limit;
    * the system HTTP transport;
    * bearer, API key header, and no-authorization handlers. Each handles a
      distinct authorization kind, so at most one can apply to a request.

    It has no default service access, because the protocol has no universal
    base URL; the endpoint always comes from the caller's service access.
    Building the binding reads no credential, environment, or network.

    Args:
        max_response_body_bytes: Largest success or error body the decoders
            accept, as a positive safe integer.
        compatibility_policy: Policy for the adapter. ``None`` uses the SDK
            default ``compatible`` policy.
        transport: Transport to share with other bindings. ``None`` creates a
            new system HTTP transport with default settings.

    Returns:
        A binding to install under :data:`OPENAI_COMPATIBLE_TYPE_KEY` and
        :data:`OPENAI_COMPATIBLE_SERVER_STREAM_TYPE_KEY`.

    Raises:
        TypeError: If ``transport`` or ``compatibility_policy`` has the wrong
            type.
        ModelInteractionError: If ``max_response_body_bytes`` is not a usable
            limit.
    """
    if transport is not None and not isinstance(
        cast(object, transport), DefaultSystemHttpTransport
    ):
        raise TypeError("transport must be a DefaultSystemHttpTransport or None.")
    return ModelIntegrationBinding(
        id=OPENAI_COMPATIBLE_BINDING_ID,
        version=OPENAI_COMPATIBLE_BINDING_VERSION,
        target_matcher=_ProtocolTargetMatcher(),
        task_matcher=_ConversationUnaryMatcher(),
        task_protocol_adapter=OpenAIChatCompletionsAdapter(compatibility_policy),
        authorization_handlers=(
            BearerAuthorizationHandler(),
            ApiKeyHeaderAuthorizationHandler(),
            NoAuthorizationHandler(),
        ),
        default_service_access=None,
        payload_encoders=(JsonPayloadEncoder(),),
        payload_decoders=(
            JsonSuccessPayloadDecoder(max_response_body_bytes),
            JsonErrorPayloadDecoder(max_response_body_bytes),
        ),
        transports=(DefaultSystemHttpTransport() if transport is None else transport,),
    )
