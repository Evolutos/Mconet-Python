"""Tests for the default OpenAI-compatible integration binding factory."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic import (
    ApiKeyHeaderAuthorizationHandler,
    BearerAuthorizationHandler,
    NoAuthorizationHandler,
)
from mconet.client._openai_compatible_binding import (
    OPENAI_COMPATIBLE_BINDING_ID,
    OPENAI_COMPATIBLE_BINDING_VERSION,
    OPENAI_COMPATIBLE_TYPE_KEY,
    openai_compatible_binding,
)
from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import (
    CompatibilityPolicy,
    Extensions,
    ModelDescriptor,
    ModelInteractionError,
    NamedModel,
    OpenIdentifier,
    default_compatibility_policy,
)
from mconet.core.runtime._integration_responsibility_chain import (
    IntegrationResponsibilityChain,
)
from mconet.core.runtime._integration_type_key import IntegrationTypeKey
from mconet.core.runtime._integration_type_table import IntegrationTypeTable
from mconet.core.runtime.default_model_integration_resolver import (
    DefaultModelIntegrationResolver,
)
from mconet.core.spi import ModelTargetMatch, RuntimeComponent, TaskMatch
from mconet.integration.openai_compatible import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    OpenAIChatCompletionsAdapter,
)
from mconet.transport.http_system import DefaultSystemHttpTransport

_LIMIT = 1_048_576
_STRICT = CompatibilityPolicy(OpenIdentifier("strict"))


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete structural task descriptor."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


def _target(
    protocol: OpenIdentifier = OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
    service: str = "service.any-vendor",
) -> _Target:
    """Build a target for one protocol and service."""
    return _Target(OpenIdentifier(service), protocol, NamedModel("any-model"))


_CONVERSATION = _Task(OpenIdentifier("conversation.generate"))
_UNARY = _Mode(OpenIdentifier("unary"))


def test_binding_combines_adapter_codecs_transport_and_handlers_explicitly() -> None:
    """Verify every role holds exactly the intended component instances."""
    binding = openai_compatible_binding(max_response_body_bytes=_LIMIT)

    assert (
        binding.id
        == OPENAI_COMPATIBLE_BINDING_ID
        == ("openai-compatible.chat-completions")
    )
    assert binding.version == OPENAI_COMPATIBLE_BINDING_VERSION == "1.0.0"
    assert isinstance(binding.task_protocol_adapter, OpenAIChatCompletionsAdapter)
    assert [type(handler) for handler in binding.authorization_handlers] == [
        BearerAuthorizationHandler,
        ApiKeyHeaderAuthorizationHandler,
        NoAuthorizationHandler,
    ]
    assert binding.default_service_access is None
    assert [type(encoder) for encoder in binding.payload_encoders] == [
        JsonPayloadEncoder
    ]
    assert [type(decoder) for decoder in binding.payload_decoders] == [
        JsonSuccessPayloadDecoder,
        JsonErrorPayloadDecoder,
    ]
    assert [type(transport) for transport in binding.transports] == [
        DefaultSystemHttpTransport
    ]
    assert dict(binding.extensions) == {}


def test_codec_ports_connect_to_the_adapter_ports() -> None:
    """Verify the encoder accepts the payload and decoders feed both inputs."""
    binding = openai_compatible_binding(max_response_body_bytes=_LIMIT)

    def port_facts(component: RuntimeComponent, side: str) -> list[tuple[object, ...]]:
        contract = component.descriptor.type_contract
        assert contract is not None
        ports = contract.inputs if side == "inputs" else contract.outputs
        return [(port.type_id, port.schema_id, port.media_type) for port in ports]

    payload = port_facts(binding.task_protocol_adapter, "outputs")
    assert port_facts(binding.payload_encoders[0], "inputs") == payload
    adapter_inputs = port_facts(binding.task_protocol_adapter, "inputs")
    for decoder, adapter_input in zip(
        binding.payload_decoders, adapter_inputs, strict=True
    ):
        assert port_facts(decoder, "outputs") == [adapter_input]


def test_type_key_is_the_chat_completions_conversation_unary_key() -> None:
    """Verify the table key names the protocol, task, and mode only."""
    assert OPENAI_COMPATIBLE_TYPE_KEY == IntegrationTypeKey(
        OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID,
        OpenIdentifier("conversation.generate"),
        OpenIdentifier("unary"),
    )
    assert OPENAI_COMPATIBLE_TYPE_KEY.serialize() == (
        "openai.chat-completions/conversation.generate/unary"
    )


def test_matchers_accept_any_service_and_model_of_the_protocol() -> None:
    """Verify the binding applies to every service using the protocol."""
    binding = openai_compatible_binding(max_response_body_bytes=_LIMIT)

    for service in ("service.openai", "service.local-gateway"):
        assert binding.target_matcher.match(_target(service=service)) == (
            ModelTargetMatch(True, 1)
        )
    assert binding.task_matcher.match(_CONVERSATION, _UNARY) == TaskMatch(True, 1)


def test_matchers_reject_another_protocol_task_or_mode() -> None:
    """Verify each matcher compares its identifiers exactly."""
    binding = openai_compatible_binding(max_response_body_bytes=_LIMIT)

    assert (
        binding.target_matcher.match(_target(OpenIdentifier("openai.responses")))
        is None
    )
    assert (
        binding.task_matcher.match(_Task(OpenIdentifier("embedding.create")), _UNARY)
        is None
    )
    assert (
        binding.task_matcher.match(
            _CONVERSATION, _Mode(OpenIdentifier("server_stream"))
        )
        is None
    )


def test_policy_and_transport_are_passed_through() -> None:
    """Verify the adapter policy and a shared transport are used as given."""
    transport = DefaultSystemHttpTransport()

    binding = openai_compatible_binding(
        max_response_body_bytes=_LIMIT,
        compatibility_policy=_STRICT,
        transport=transport,
    )
    default = openai_compatible_binding(max_response_body_bytes=_LIMIT)

    adapter = cast(OpenAIChatCompletionsAdapter, binding.task_protocol_adapter)
    assert adapter.compatibility_policy is _STRICT
    assert binding.transports[0] is transport
    default_adapter = cast(OpenAIChatCompletionsAdapter, default.task_protocol_adapter)
    assert default_adapter.compatibility_policy == default_compatibility_policy()
    assert default.transports[0] is not transport


def test_each_call_builds_independent_component_instances() -> None:
    """Verify bindings never share mutable component state implicitly."""
    first = openai_compatible_binding(max_response_body_bytes=_LIMIT)
    second = openai_compatible_binding(max_response_body_bytes=_LIMIT)

    assert first.task_protocol_adapter is not second.task_protocol_adapter
    assert first.payload_decoders[0] is not second.payload_decoders[0]
    assert first.transports[0] is not second.transports[0]


def test_factory_rejects_invalid_limits_and_transports() -> None:
    """Verify bad inputs fail while the binding is built."""
    for limit in (0, -1, 2**53):
        error = _capture(
            lambda limit=limit: openai_compatible_binding(max_response_body_bytes=limit)
        )

        assert isinstance(error, ModelInteractionError)

    error = _capture(
        lambda: openai_compatible_binding(
            max_response_body_bytes=_LIMIT,
            transport=cast(DefaultSystemHttpTransport, object()),
        )
    )
    assert isinstance(error, TypeError)


def test_default_resolver_resolves_the_binding_by_exact_key_in_strict_mode() -> None:
    """Verify the binding resolves without the compatibility chain."""
    binding = openai_compatible_binding(max_response_body_bytes=_LIMIT)
    resolver = DefaultModelIntegrationResolver(
        IntegrationTypeTable(((OPENAI_COMPATIBLE_TYPE_KEY, binding),)),
        IntegrationResponsibilityChain(()),
    )

    plan = resolver.resolve(_target(), _CONVERSATION, _UNARY, _STRICT)

    assert plan.binding_id == OPENAI_COMPATIBLE_BINDING_ID
    assert plan.task_protocol_adapter is binding.task_protocol_adapter
    assert plan.payload_decoders == binding.payload_decoders
    assert plan.transports == binding.transports
