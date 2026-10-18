"""Task protocol adapter for OpenAI-compatible text chat completions."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    ConversationTaskResult,
    ErrorCategory,
    InteractionMode,
    InteractionPhase,
    JsonValue,
    MediaType,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    OpenIdentifier,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    TaskDescriptor,
    UriValue,
    default_compatibility_policy,
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
    TransportResponseMetadata,
    TransportSelection,
)
from mconet.integration.openai_compatible._conversation import conversation_input
from mconet.integration.openai_compatible._errors import service_error
from mconet.integration.openai_compatible._messages import wire_messages
from mconet.integration.openai_compatible._openai_chat_completion_error_response_dto import (
    OpenAIChatCompletionErrorResponseDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_request_dto import (
    OpenAIChatCompletionRequestDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_response_dto import (
    OpenAIChatCompletionResponseDTO,
)
from mconet.integration.openai_compatible._parameters import wire_parameters
from mconet.integration.openai_compatible._policy import enforces_wire_profile
from mconet.integration.openai_compatible._response import (
    output_messages,
    output_status,
    resolved_model,
    single_choice,
    token_usage,
)
from mconet.integration.openai_compatible._server_stream import (
    OpenAIServerStreamMapper,
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
_SERVER_STREAM_MODE_ID = OpenIdentifier("server_stream")
_STREAM_EXTENSION = "mconet.openai.stream"
_STREAM_MAPPER_EXTENSION = "mconet.server_stream.mapper"
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

    The adapter holds only its immutable compatibility policy. It handles
    exactly two combinations: a target whose protocol is
    ``openai.chat-completions``, the ``conversation.generate`` task, and either
    the ``unary`` or the ``server_stream`` interaction mode. Any service and
    model may use the protocol, so neither is part of matching.

    The policy only decides request values outside the frozen wire profile:
    ``strict`` and unknown modes reject unknown roles and a ``temperature``
    above 2, while ``compatible`` and ``permissive`` send them unchanged. The
    SPI has no diagnostics output, so a relaxed mode adds no diagnostic.
    Structural rules, responses, and errors never depend on the policy.

    Its payload output and both decoded inputs are ``json.value`` values of
    media type ``application/json``, matching the JSON codec ports.
    """

    __slots__ = ("_compatibility_policy", "_enforce_profile")

    def __init__(self, compatibility_policy: CompatibilityPolicy | None = None) -> None:
        """Create the adapter for one compatibility policy.

        Args:
            compatibility_policy: Policy for request values outside the wire
                profile. ``None`` uses the SDK default ``compatible`` policy.

        Raises:
            TypeError: If the policy is not a CompatibilityPolicy.
        """
        policy = (
            default_compatibility_policy()
            if compatibility_policy is None
            else compatibility_policy
        )
        if not isinstance(cast(object, policy), CompatibilityPolicy):
            raise TypeError(
                "OpenAIChatCompletionsAdapter compatibility_policy must be a "
                "CompatibilityPolicy."
            )
        self._compatibility_policy = policy
        # The decision is fixed at construction so every request of this
        # adapter instance is mapped under the same policy.
        self._enforce_profile = enforces_wire_profile(policy)

    @property
    def compatibility_policy(self) -> CompatibilityPolicy:
        """Return the policy used for request values outside the profile."""
        return self._compatibility_policy

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
            generation task, and the unary or server-stream mode.
        """
        # Unary and server stream share this protocol. Other modes stay
        # unsupported until their own request and response contracts exist.
        return (
            target.protocol_id == OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
            and task.type == _CONVERSATION_TASK_TYPE
            and mode.id in (_UNARY_MODE_ID, _SERVER_STREAM_MODE_ID)
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
        del request
        endpoint = _profile_endpoint(access.endpoint)
        # The stream flag and mapper travel on the plan so request encoding
        # can set ``stream`` without the runtime importing this protocol. A
        # unary plan keeps the extensions empty.
        extensions: dict[str, object] = {}
        if mode.id == _SERVER_STREAM_MODE_ID:
            extensions[_STREAM_EXTENSION] = True
            # A new mapper per plan keeps argument fragments from one stream
            # from being appended onto another interaction's calls.
            extensions[_STREAM_MAPPER_EXTENSION] = OpenAIServerStreamMapper()
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
            extensions=extensions,
        )

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return the chat completion body paired with the prepared plan.

        The body is ``model`` (the target model name), ``messages`` (input
        entries in preorder, with tool calls folded into the preceding
        assistant message and tool results sent as their own messages), the
        set sampling members, ``tools`` and ``tool_choice`` when the caller
        set them, and ``stream`` set from the plan, in profile order. Unary
        plans send ``false``. Server-stream plans send ``true``. The body is
        not encoded here.

        Args:
            request: Validated conversation request.
            plan: Plan from :meth:`prepare_plan`, kept by identity because
                components were already selected from it.

        Returns:
            A request plan whose payload is a ``json.value`` holding the body.

        Raises:
            ModelInteractionError: If the task is not a ConversationTaskRequest,
                the conversation has no entry or an unsupported role, content,
                or element, or the policy rejects a parameter value.
        """
        messages, parameters = conversation_input(request.task)
        members = wire_parameters(parameters, enforce_profile=self._enforce_profile)
        body = OpenAIChatCompletionRequestDTO(
            model=request.target.model.name,
            messages=wire_messages(messages, enforce_profile=self._enforce_profile),
            temperature=members.temperature,
            top_p=members.top_p,
            max_tokens=members.max_tokens,
            stop=members.stop,
            seed=members.seed,
            tools=members.tools,
            tool_choice=members.tool_choice,
            stream=plan.extensions.get(_STREAM_EXTENSION) is True,
        )
        payload = ErasedRuntimeValue(_JSON_VALUE_TYPE_ID, body.to_json())
        return ProtocolRequestPlan(payload, plan)

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Return the service-reported facts of one decoded success body.

        The single choice message becomes the result MessageDocument, and the
        choice's extra members become result extensions. ``finish_reason``
        gives both the status and the exact stop reason. ``usage`` and
        ``model`` are copied when sent and stay ``None`` otherwise; the
        request target is never consulted. The response ``id`` and unknown
        top-level members become response extensions.

        Args:
            response: Decoded ``json.value`` success payload.

        Returns:
            The parsed service facts. No ModelOutput is built here.

        Raises:
            ModelInteractionError: If the body violates the wire profile, does
                not have exactly one choice, has an unknown message role, or
                reports an empty model name.
        """
        body = OpenAIChatCompletionResponseDTO.from_json(
            cast(JsonValue, response.value)
        )
        choice = single_choice(body)
        extensions: dict[str, JsonValue] = {}
        if body.id is not None:
            extensions["id"] = body.id
        extensions.update(body.extensions)
        return ParsedTaskResponse(
            result=ConversationTaskResult(
                output_messages(choice), extensions=choice.extensions
            ),
            status=output_status(choice.finish_reason),
            resolved_model=resolved_model(body.model),
            stop_reason=choice.finish_reason,
            usage=token_usage(body.usage),
            extensions=extensions,
        )

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Return the normalized error for one decoded failure body.

        Args:
            error: Decoded ``json.value`` failure payload.
            metadata: Transport facts of the failed response.

        Returns:
            The mapped error, or ``None`` when the payload is not an
            ``{"error": {...}}`` body, so the runtime builds its fallback
            error from the transport facts.
        """
        try:
            body = OpenAIChatCompletionErrorResponseDTO.from_json(
                cast(JsonValue, error.value)
            )
        except ModelInteractionError:
            # Gateways and proxies often answer with their own JSON. That is
            # an unrecognized shape, not a second failure to report.
            return None
        return service_error(body, metadata)


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
