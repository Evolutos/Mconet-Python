"""SPI validation for directly injected runtime components."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.runtime._runtime_components_spi_validation import (
    validate_runtime_components_spi,
)
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    ComponentDescriptor,
    ModelIntegrationResolver,
    PayloadDecoder,
    PayloadEncoder,
    RuntimeComponents,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
)

_SINGLE_FIELDS = (
    "model_integration_resolver",
    "task_protocol_adapter",
    "service_access_resolver",
    "payload_encoder",
    "success_payload_decoder",
    "error_payload_decoder",
    "transport",
    "authorization_handler_resolver",
)


class _Metadata:
    """Descriptor-only object that does not implement a behavior protocol."""

    def __init__(self) -> None:
        """Store nominal metadata without behavior methods."""
        self.descriptor = ComponentDescriptor("metadata", "1.0.0", "application")
        self.calls: list[str] = []


class _Encoder:
    """Encoder behavior that must not be accepted as another role."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("encoder", "1.0.0", "application")
        self.calls: list[str] = []

    def encode(self, payload: object) -> object:
        """Record an encode call that validation must not make."""
        del payload
        self.calls.append("encode")
        return None


class _Behavior:
    """One instance that structurally implements every injected role."""

    def __init__(self, *, descriptor: object | None = None) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = (
            ComponentDescriptor("behavior", "1.0.0", "application")
            if descriptor is None
            else descriptor
        )
        self.calls: list[str] = []

    def resolve(self, *values: object) -> object:
        """Record a resolve call that validation must not make."""
        del values
        self.calls.append("resolve")
        return None

    def supports(self, *values: object) -> object:
        """Record a supports call that validation must not make."""
        del values
        self.calls.append("supports")
        return None

    def prepare_plan(self, *values: object) -> object:
        """Record a planning call that validation must not make."""
        del values
        self.calls.append("prepare_plan")
        return None

    def build_request(self, *values: object) -> object:
        """Record a request build that validation must not make."""
        del values
        self.calls.append("build_request")
        return None

    def parse_response(self, *values: object) -> object:
        """Record a success parse that validation must not make."""
        del values
        self.calls.append("parse_response")
        return None

    def parse_error(self, *values: object) -> object:
        """Record an error parse that validation must not make."""
        del values
        self.calls.append("parse_error")
        return None

    def encode(self, payload: object) -> object:
        """Record an encode call that validation must not make."""
        del payload
        self.calls.append("encode")
        return None

    def decode(self, raw_data: object) -> object:
        """Record a decode call that validation must not make."""
        del raw_data
        self.calls.append("decode")
        return None

    async def send(self, *values: object) -> object:
        """Record a send call that validation must not make."""
        del values
        self.calls.append("send")
        return None

    async def apply(self, *values: object) -> None:
        """Record an apply call that validation must not make."""
        del values
        self.calls.append("apply")


def _expect(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require one exception whose message contains the stable fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _with_field(field_name: str, value: object) -> RuntimeComponents:
    """Place one object into a single role field."""
    if field_name == "model_integration_resolver":
        return RuntimeComponents(
            model_integration_resolver=cast(ModelIntegrationResolver, value)
        )
    if field_name == "task_protocol_adapter":
        return RuntimeComponents(task_protocol_adapter=cast(TaskProtocolAdapter, value))
    if field_name == "service_access_resolver":
        return RuntimeComponents(
            service_access_resolver=cast(ServiceAccessResolver, value)
        )
    if field_name == "payload_encoder":
        return RuntimeComponents(payload_encoder=cast(PayloadEncoder, value))
    if field_name == "success_payload_decoder":
        return RuntimeComponents(success_payload_decoder=cast(PayloadDecoder, value))
    if field_name == "error_payload_decoder":
        return RuntimeComponents(error_payload_decoder=cast(PayloadDecoder, value))
    if field_name == "transport":
        return RuntimeComponents(transport=cast(Transport, value))
    if field_name == "authorization_handler_resolver":
        return RuntimeComponents(
            authorization_handler_resolver=cast(AuthorizationHandlerResolver, value)
        )
    raise AssertionError(f"Unexpected field {field_name}.")


def test_empty_components_keep_their_identity() -> None:
    """Accept an unset carrier without copying it."""
    components = RuntimeComponents()
    assert validate_runtime_components_spi(components) is components


def test_each_metadata_only_role_fails_its_own_protocol() -> None:
    """Reject a descriptor-only instance in every single-value field."""
    metadata = _Metadata()
    for field_name in _SINGLE_FIELDS:
        components = _with_field(field_name, metadata)
        _expect(
            TypeError,
            lambda components=components: validate_runtime_components_spi(components),
            f"{field_name} must implement the declared behavior protocol",
        )
        assert metadata.calls == []


def test_encoder_is_rejected_when_injected_as_transport() -> None:
    """Reject a behavior that implements a different field protocol."""
    encoder = _Encoder()
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, encoder))
    assert validate_runtime_components_spi(components) is components
    assert encoder.calls == []

    mismatched = RuntimeComponents(transport=cast(Transport, encoder))
    _expect(
        TypeError,
        lambda: validate_runtime_components_spi(mismatched),
        "transport must implement the declared behavior protocol",
    )
    assert encoder.calls == []


def test_present_roles_match_their_protocols_without_being_called() -> None:
    """Accept one structural instance in every field and leave it idle."""
    behavior = _Behavior()
    components = RuntimeComponents(
        model_integration_resolver=cast(ModelIntegrationResolver, behavior),
        task_protocol_adapter=cast(TaskProtocolAdapter, behavior),
        service_access_resolver=cast(ServiceAccessResolver, behavior),
        payload_encoder=cast(PayloadEncoder, behavior),
        success_payload_decoder=cast(PayloadDecoder, behavior),
        error_payload_decoder=cast(PayloadDecoder, behavior),
        transport=cast(Transport, behavior),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, behavior),
        authorization_handlers=(cast(AuthorizationHandler, behavior),),
    )
    assert validate_runtime_components_spi(components) is components
    assert behavior.calls == []


def test_behavior_with_a_non_nominal_descriptor_is_rejected() -> None:
    """Reject protocol members whose descriptor is not component metadata."""
    behavior = _Behavior(descriptor="not-metadata")
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, behavior))
    _expect(
        TypeError,
        lambda: validate_runtime_components_spi(components),
        "payload_encoder descriptor must be a ComponentDescriptor",
    )
    assert behavior.calls == []


def test_handler_candidates_must_be_an_immutable_protocol_tuple() -> None:
    """Reject a mutable handler collection and a non-handler candidate."""
    mutable = RuntimeComponents(
        authorization_handlers=cast(tuple[AuthorizationHandler, ...], [])
    )
    _expect(
        TypeError,
        lambda: validate_runtime_components_spi(mutable),
        "authorization_handlers must be a tuple",
    )

    metadata = _Metadata()
    components = RuntimeComponents(
        authorization_handlers=(cast(AuthorizationHandler, metadata),)
    )
    _expect(
        TypeError,
        lambda: validate_runtime_components_spi(components),
        "authorization_handlers must implement the declared behavior protocol",
    )
    assert metadata.calls == []


def test_non_carrier_is_rejected_before_role_checks() -> None:
    """Reject a value that is not a runtime component carrier."""
    _expect(
        TypeError,
        lambda: validate_runtime_components_spi(cast(RuntimeComponents, object())),
        "components must be a RuntimeComponents",
    )
