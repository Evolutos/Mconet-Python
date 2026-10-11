"""Tests for the OpenAI-compatible chat completions adapter."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from mconet.core.domain import (
    ConversationInputNode,
    ConversationTaskBuilder,
    ConversationTaskResult,
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    HeaderField,
    Headers,
    MediaType,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelRequestBuilder,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedServiceAccess,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TextMessageContent,
    UriValue,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentTypePort,
    DecoderSelection,
    EncoderSelection,
    TransportSelection,
)
from mconet.integration.openai_compatible.openai_chat_completions_adapter import (
    CHAT_COMPLETIONS_PATH,
    INVALID_SERVICE_ENDPOINT_CODE,
    MISSING_SERVICE_ENDPOINT_CODE,
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)

_JSON = MediaType("application", "json")
_JSON_VALUE = OpenIdentifier("json.value")
_SERVICE_ID = OpenIdentifier("service.vendor")
_UNARY = OpenIdentifier("unary")
_CONVERSATION = OpenIdentifier("conversation.generate")
_ENDPOINT = UriValue("https://models.example.test", True)
_NO_AUTHORIZATION = OpenIdentifier("authorization.none")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for fixtures."""
    return {}


def _model() -> ModelDescriptor:
    """Return the requested fixture model."""
    return NamedModel("fixture-model")


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete ModelTarget for adapter tests."""

    protocol_id: OpenIdentifier = OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID
    service_id: OpenIdentifier = _SERVICE_ID
    model: ModelDescriptor = field(default_factory=_model)
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Complete InteractionMode for adapter tests."""

    id: OpenIdentifier = _UNARY


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete TaskDescriptor for adapter tests."""

    type: OpenIdentifier = _CONVERSATION
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Kind:
    """Complete MessageElementKind for fixture documents."""

    id: OpenIdentifier
    category: str = "group"
    composition: Literal["leaf", "container"] = "container"


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Complete TaskNodeKind for fixture task documents."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"] = "container"


@dataclass(frozen=True, slots=True)
class _Role:
    """Complete MessageRole for fixture entries."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization value carried through the plan."""

    kind: OpenIdentifier = _NO_AUTHORIZATION


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _entry(entry_id: str, role_id: str, text: str) -> MessageEntry:
    """Create one single-text entry."""
    return MessageEntry(
        entry_id,
        _Role(OpenIdentifier(role_id)),
        (TextMessageContent(f"{entry_id}-text", text),),
    )


def _request(
    parameters: GenerationParameters | None = None,
    target: _Target | None = None,
) -> ModelRequest:
    """Create one validated conversation request."""
    root = MessageGroup(
        "root",
        _Kind(OpenIdentifier("message.root")),
        (
            _entry("system", "message.system", "Be exact."),
            _entry("user", "message.user", "Hi"),
        ),
    )
    children: tuple[TaskNode, ...] = (
        ConversationInputNode("input", MessageDocument("1.0", "input", root)),
    )
    if parameters is not None:
        children = (*children, GenerationParametersNode("parameters", parameters))
    document = TaskDocument(
        "1.0", TaskGroupNode("root", _TaskKind(OpenIdentifier("task.root")), children)
    )
    task = ConversationTaskBuilder(document).build()
    return ModelRequestBuilder(target or _Target(), task).build()


def _access(endpoint: UriValue | None = _ENDPOINT) -> ResolvedServiceAccess:
    """Create resolved access with ordered headers and query values."""
    return ResolvedServiceAccess(
        endpoint=endpoint,
        authorization=_Authorization(),
        headers=Headers((HeaderField("X-Trace", "a"), HeaderField("x-trace", "b"))),
        query=QueryParameters((QueryParameter("api-version", "2026-10"),)),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )


def test_descriptor_declares_json_value_ports() -> None:
    """Verify the adapter ports connect to the JSON codec ports."""
    descriptor = OpenAIChatCompletionsAdapter().descriptor

    assert descriptor.name == "openai-chat-completions-adapter"
    assert descriptor.version == "1.0.0"
    assert descriptor.source == "builtin"
    assert descriptor.capabilities == frozenset()
    assert descriptor.type_contract is not None
    assert descriptor.type_contract.inputs == (
        ComponentTypePort("response", _JSON_VALUE, None, _JSON),
        ComponentTypePort("error", _JSON_VALUE, None, _JSON),
    )
    assert descriptor.type_contract.outputs == (
        ComponentTypePort("payload", _JSON_VALUE, None, _JSON),
    )
    assert OpenAIChatCompletionsAdapter().descriptor is descriptor


def test_supports_the_chat_completions_protocol_for_any_service_and_model() -> None:
    """Verify the protocol id selects the adapter, not the service or model."""
    adapter = OpenAIChatCompletionsAdapter()
    other_service = _Target(
        service_id=OpenIdentifier("service.other"),
        model=NamedModel("another-model"),
        deployment_id="east",
    )

    assert adapter.supports(_Target(), _Task(), _Mode()) is True
    assert adapter.supports(other_service, _Task(), _Mode()) is True


def test_does_not_support_another_protocol() -> None:
    """Verify protocol identity is matched exactly."""
    adapter = OpenAIChatCompletionsAdapter()

    for protocol_id in ("openai.responses", "openai.chat-completions.v2", "openai"):
        target = _Target(protocol_id=OpenIdentifier(protocol_id))
        assert adapter.supports(target, _Task(), _Mode()) is False


def test_does_not_support_another_task_type() -> None:
    """Verify only conversation generation is handled."""
    adapter = OpenAIChatCompletionsAdapter()

    for task_type in ("embedding.generate", "conversation.summarize"):
        task = _Task(type=OpenIdentifier(task_type))
        assert adapter.supports(_Target(), task, _Mode()) is False


def test_does_not_support_another_interaction_mode() -> None:
    """Verify only unary mode is handled."""
    adapter = OpenAIChatCompletionsAdapter()

    for mode_id in ("streaming", "batch"):
        assert adapter.supports(_Target(), _Task(), _Mode(OpenIdentifier(mode_id))) is (
            False
        )


def test_supports_the_descriptors_of_real_conversation_values() -> None:
    """Verify the standard conversation request and result descriptors match."""
    adapter = OpenAIChatCompletionsAdapter()
    root = MessageGroup("root", _root_kind(), ())
    result = ConversationTaskResult(MessageDocument("1.0", "output", root))

    assert adapter.supports(_Target(), result.descriptor, _Mode())
    assert adapter.supports(_Target(), _request().task.descriptor, _Mode())


def _root_kind() -> MessageElementKind:
    """Return the standard message root kind."""
    return _Kind(OpenIdentifier("message.root"))


def test_prepare_plan_fixes_the_profile_request_and_json_selections() -> None:
    """Verify every planned fact of the endpoint and wire profiles."""
    access = _access()

    plan = OpenAIChatCompletionsAdapter().prepare_plan(_request(), access, _Mode())

    transport_plan = plan.transport_plan
    assert transport_plan.endpoint is access.endpoint
    assert transport_plan.path == CHAT_COMPLETIONS_PATH == "/v1/chat/completions"
    assert transport_plan.method == "POST"
    assert transport_plan.headers is access.headers
    assert transport_plan.query is access.query
    assert transport_plan.authorization is access.authorization
    assert transport_plan.body_signing_requirement == BodySigningRequirement()
    assert dict(transport_plan.transport_extensions) == {}
    assert plan.payload_encoder == EncoderSelection(_JSON)
    assert plan.success_decoder == DecoderSelection(_JSON)
    assert plan.error_decoder == DecoderSelection(_JSON)
    assert plan.transport == TransportSelection(OpenIdentifier("http"))
    assert plan.mode_components == ()
    assert plan.type_contract is OpenAIChatCompletionsAdapter().descriptor.type_contract
    assert dict(plan.extensions) == {}


def test_prepare_plan_does_not_depend_on_request_content() -> None:
    """Verify parameters and models do not change the plan."""
    adapter = OpenAIChatCompletionsAdapter()
    access = _access()
    other = _request(
        GenerationParameters(temperature=0.5),
        _Target(model=NamedModel("another-model")),
    )

    assert adapter.prepare_plan(_request(), access, _Mode()) == adapter.prepare_plan(
        other, access, _Mode()
    )


def test_prepare_plan_requires_an_endpoint() -> None:
    """Verify planning fails without a resolved endpoint."""
    error = _capture(
        lambda: OpenAIChatCompletionsAdapter().prepare_plan(
            _request(), _access(None), _Mode()
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "invalid_request"
    assert error.phase.id.value == "protocol_planning"
    assert error.code == MISSING_SERVICE_ENDPOINT_CODE
    assert error.message == (
        "The OpenAI-compatible chat completions protocol requires a service endpoint."
    )


def test_prepare_plan_rejects_endpoints_the_profile_forbids_without_echoing() -> None:
    """Verify relative, query, and fragment endpoints fail with a fixed message."""
    adapter = OpenAIChatCompletionsAdapter()

    for endpoint in (
        UriValue("https://models.example.test/?key=token-value", True),
        UriValue("https://models.example.test/#token-value", True),
        UriValue("/v1", False),
    ):
        access = _access(endpoint)
        error = _capture(
            lambda access=access: adapter.prepare_plan(_request(), access, _Mode())
        )

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "invalid_request"
        assert error.phase.id.value == "protocol_planning"
        assert error.code == INVALID_SERVICE_ENDPOINT_CODE
        assert error.message == (
            "The OpenAI-compatible service endpoint must be an absolute URI "
            "without a query or fragment."
        )
        assert "token-value" not in str(error)


def test_prepare_plan_keeps_an_endpoint_with_a_base_path() -> None:
    """Verify a base path is allowed and left for runtime joining."""
    endpoint = UriValue("https://gateway.example.test/openai", True)

    plan = OpenAIChatCompletionsAdapter().prepare_plan(
        _request(), _access(endpoint), _Mode()
    )

    assert plan.transport_plan.endpoint is endpoint
    assert plan.transport_plan.path == "/v1/chat/completions"
