"""Task protocol adapter for OpenAI-compatible text chat completions."""

from __future__ import annotations

from mconet.core.domain import (
    ErrorCategory,
    InteractionMode,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    OpenIdentifier,
    ResolvedServiceAccess,
    TaskDescriptor,
    UriValue,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TransportRequestPlan,
    TransportSelection,
)
from mconet.integration.openai_compatible._conversation import conversation_input
from mconet.integration.openai_compatible._messages import wire_messages
from mconet.integration.openai_compatible._parameters import wire_parameters
from mconet.integration.openai_compatible.openai_chat_completion_request_dto import (
    OpenAIChatCompletionRequestDTO,
)

OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID = OpenIdentifier("openai.chat-completions")
"""Protocol identifier a ModelTarget names to select this adapter."""

MISSING_SERVICE_ENDPOINT_CODE = "missing_service_endpoint"
"""Stable code for planning without a resolved service endpoint."""

INVALID_SERVICE_ENDPOINT_CODE = "invalid_service_endpoint"
"""Stable code for an endpoint the endpoint profile does not allow."""

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
"""Request path of the frozen endpoint profile, including its version."""

_CONVERSATION_TASK_TYPE = OpenIdentifier("conversation.generate")
_UNARY_MODE_ID = OpenIdentifier("unary")
_JSON_VALUE_TYPE_ID = OpenIdentifier("json.value")
_JSON_MEDIA_TYPE = MediaType("application", "json")
_HTTP_TRANSPORT_KIND = OpenIdentifier("http")
_POST_METHOD = "POST"
_INVALID_REQUEST = ErrorCategory(OpenIdentifier("invalid_request"))
_PROTOCOL_PLANNING = InteractionPhase(OpenIdentifier("protocol_planning"))

_ADAPTER_TYPE_CONTRACT = ComponentTypeContract(
    inputs=(
        ComponentTypePort("response", _JSON_VALUE_TYPE_ID, None, _JSON_MEDIA_TYPE),
        ComponentTypePort("error", _JSON_VALUE_TYPE_ID, None, _JSON_MEDIA_TYPE),
    ),
    outputs=(
        ComponentTypePort("payload", _JSON_VALUE_TYPE_ID, None, _JSON_MEDIA_TYPE),
    ),
)

_ADAPTER_DESCRIPTOR = ComponentDescriptor(
    "openai-chat-completions-adapter",
    "1.0.0",
    "builtin",
    _ADAPTER_TYPE_CONTRACT,
)


class OpenAIChatCompletionsAdapter:
    """Map conversation tasks to the OpenAI-compatible chat completions API.

    The adapter is stateless. It handles exactly one combination: a target
    whose protocol is ``openai.chat-completions``, the
    ``conversation.generate`` task, and the ``unary`` interaction mode. Any
    service and model may use the protocol, so neither is part of matching.

    Its payload output and both decoded inputs are ``json.value`` values of
    media type ``application/json``, matching the JSON codec ports.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared diagnostic metadata and JSON type contract."""
        return _ADAPTER_DESCRIPTOR

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Return whether the target, task, and mode are the handled tuple.

        Each identifier is compared exactly. Service, model, deployment, task
        version, and extensions are not consulted, and no I/O happens.

        Args:
            target: Model target being matched.
            task: Descriptor of the requested task.
            mode: Requested interaction mode.

        Returns:
            ``True`` only for the chat completions protocol, the conversation
            generation task, and unary mode.
        """
        return (
            target.protocol_id == OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
            and task.type == _CONVERSATION_TASK_TYPE
            and mode.id == _UNARY_MODE_ID
        )

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Return the fixed execution requirements for one chat completion.

        The plan sends ``POST /v1/chat/completions`` to the resolved endpoint
        with the resolved headers, query, and authorization, and no body
        signing. The payload and both responses are ``application/json``, and
        the transport is HTTP. Nothing is encoded, no credential is read, and
        no I/O happens.

        Args:
            request: Validated request. Planning does not depend on its content.
            access: Resolved service access for the interaction.
            mode: Interaction mode, already matched by :meth:`supports`.

        Returns:
            A plan whose type contract is the adapter's JSON value contract.

        Raises:
            ModelInteractionError: If access has no endpoint, or the endpoint
                is not absolute or has a query or fragment. Endpoint text is
                never copied into the error.
        """
        del request, mode
        endpoint = _profile_endpoint(access.endpoint)
        return ProtocolExecutionPlan(
            transport_plan=TransportRequestPlan(
                endpoint=endpoint,
                path=CHAT_COMPLETIONS_PATH,
                method=_POST_METHOD,
                headers=access.headers,
                query=access.query,
                authorization=access.authorization,
                body_signing_requirement=BodySigningRequirement(),
            ),
            payload_encoder=EncoderSelection(_JSON_MEDIA_TYPE),
            success_decoder=DecoderSelection(_JSON_MEDIA_TYPE),
            error_decoder=DecoderSelection(_JSON_MEDIA_TYPE),
            transport=TransportSelection(_HTTP_TRANSPORT_KIND),
            type_contract=_ADAPTER_TYPE_CONTRACT,
        )

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return the chat completion body paired with the prepared plan.

        The body is ``model`` (the target model name), ``messages`` (input
        entries in preorder), the set sampling members, and
        ``"stream": false``, in profile order. It is not encoded here.

        Args:
            request: Validated conversation request.
            plan: Plan from :meth:`prepare_plan`, kept by identity because
                components were already selected from it.

        Returns:
            A request plan whose payload is a ``json.value`` holding the body.

        Raises:
            ModelInteractionError: If the task is not a ConversationTaskRequest,
                or the conversation has no entry or an unsupported role,
                content, or element.
        """
        messages, parameters = conversation_input(request.task)
        members = wire_parameters(parameters)
        body = OpenAIChatCompletionRequestDTO(
            model=request.target.model.name,
            messages=wire_messages(messages),
            temperature=members.temperature,
            top_p=members.top_p,
            max_tokens=members.max_tokens,
            stop=members.stop,
            seed=members.seed,
        )
        payload = ErasedRuntimeValue(_JSON_VALUE_TYPE_ID, body.to_json())
        return ProtocolRequestPlan(payload, plan)


def _profile_endpoint(endpoint: UriValue | None) -> UriValue:
    """Return the endpoint when it satisfies the base URL profile.

    The profile takes the base URL from service access and forbids a query and
    a fragment. In a valid URI the first ``?`` or ``#`` always starts one of
    those parts, so their absence proves there is neither.

    Args:
        endpoint: Endpoint of the resolved service access.

    Returns:
        The same endpoint value.

    Raises:
        ModelInteractionError: If the endpoint is absent or not allowed.
    """
    if endpoint is None:
        raise ModelInteractionError(
            category=_INVALID_REQUEST,
            phase=_PROTOCOL_PLANNING,
            code=MISSING_SERVICE_ENDPOINT_CODE,
            message=(
                "The OpenAI-compatible chat completions protocol requires a "
                "service endpoint."
            ),
        )
    text = endpoint.value
    if not endpoint.is_absolute or "?" in text or "#" in text:
        # The endpoint can carry credentials or tenant data, so the message
        # states the rule without the value.
        raise ModelInteractionError(
            category=_INVALID_REQUEST,
            phase=_PROTOCOL_PLANNING,
            code=INVALID_SERVICE_ENDPOINT_CODE,
            message=(
                "The OpenAI-compatible service endpoint must be an absolute URI "
                "without a query or fragment."
            ),
        )
    return endpoint
