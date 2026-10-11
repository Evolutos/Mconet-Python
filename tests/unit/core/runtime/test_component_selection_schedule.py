"""Tests for fixed-priority component selection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mconet.core.domain import (
    Bytes,
    Headers,
    InteractionMode,
    MediaType,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    OpenIdentifier,
    ParsedTaskResponse,
    QueryParameters,
    ResolvedServiceAccess,
    TaskDescriptor,
    UriValue,
)
from mconet.core.runtime._component_selection_schedule import (
    select_execution_components,
)
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentDescriptor,
    ComponentSelectionResolution,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelTargetMatch,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    RuntimeComponents,
    TaskMatch,
    TransportBody,
    TransportContext,
    TransportRequest,
    TransportRequestPlan,
    TransportResponse,
    TransportResponseMetadata,
    TransportSelection,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _descriptor(name: str) -> ComponentDescriptor:
    """Return diagnostic metadata that is not used as a selection key."""
    return ComponentDescriptor(name, "1.0.0", "application")


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization with no credential payload."""

    kind: OpenIdentifier


class _Adapter:
    """Adapter stub that selection must not execute."""

    def __init__(self, name: str) -> None:
        """Store diagnostic metadata."""
        self.descriptor = _descriptor(name)

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Fail if selection calls the adapter."""
        del target, task, mode
        raise AssertionError("supports must not be called.")

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Fail if selection plans a request."""
        del request, access, mode
        raise AssertionError("prepare_plan must not be called.")

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Fail if selection builds a request."""
        del request, plan
        raise AssertionError("build_request must not be called.")

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Fail if selection parses a response."""
        del response
        raise AssertionError("parse_response must not be called.")

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Fail if selection parses an error."""
        del error, metadata
        raise AssertionError("parse_error must not be called.")


class _Encoder:
    """Encoder stub that selection must not execute."""

    def __init__(self, name: str) -> None:
        """Store diagnostic metadata."""
        self.descriptor = _descriptor(name)

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Fail if selection encodes a payload."""
        del payload
        raise AssertionError("encode must not be called.")


class _Decoder:
    """Decoder stub that selection must not execute."""

    def __init__(self, name: str) -> None:
        """Store diagnostic metadata."""
        self.descriptor = _descriptor(name)

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Fail if selection decodes a response."""
        del raw_data
        raise AssertionError("decode must not be called.")


class _Transport:
    """Transport stub that selection must not execute."""

    def __init__(self, name: str) -> None:
        """Store diagnostic metadata."""
        self.descriptor = _descriptor(name)

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Fail if selection sends a request."""
        del request, context
        raise AssertionError("send must not be called.")


def _execution_plan() -> ProtocolExecutionPlan:
    """Return one plan inside the R1 unary JSON HTTP scope."""
    media_type = MediaType("application", "json")
    return ProtocolExecutionPlan(
        transport_plan=TransportRequestPlan(
            endpoint=UriValue("https://models.example.test", True),
            path="/v1/chat/completions",
            method="POST",
            headers=Headers(),
            query=QueryParameters(),
            authorization=_Authorization(OpenIdentifier("authorization.none")),
            body_signing_requirement=BodySigningRequirement(),
        ),
        payload_encoder=EncoderSelection(media_type),
        success_decoder=DecoderSelection(media_type),
        error_decoder=DecoderSelection(media_type),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def _direct_plan(adapter: _Adapter) -> ModelIntegrationPlan:
    """Return a direct plan whose only component is the adapter."""
    return ModelIntegrationPlan(
        source="direct_adapter",
        binding_id=None,
        binding_version=None,
        match=None,
        task_protocol_adapter=adapter,
    )


def _sdk(
    encoder: _Encoder | None = None,
    *,
    include_transport: bool = True,
) -> RuntimeComponents:
    """Return SDK defaults, optionally replacing the encoder or transport."""
    return RuntimeComponents(
        task_protocol_adapter=_Adapter("sdk-adapter"),
        payload_encoder=_Encoder("sdk-encoder") if encoder is None else encoder,
        success_payload_decoder=_Decoder("sdk-success"),
        error_payload_decoder=_Decoder("sdk-error"),
        transport=_Transport("sdk-transport") if include_transport else None,
    )


def test_source_priority_is_interaction_client_plan_then_sdk() -> None:
    """Verify each higher present layer blocks every lower encoder source."""
    interaction_encoder = _Encoder("interaction-encoder")
    client_encoder = _Encoder("client-encoder")
    plan_encoder = _Encoder("plan-encoder")
    sdk_encoder = _Encoder("sdk-encoder")
    mode = _Mode(OpenIdentifier("unary"))
    execution_plan = _execution_plan()

    interaction_selected = select_execution_components(
        mode,
        execution_plan,
        _resolved_plan(payload_encoders=(plan_encoder,)),
        interaction_components=RuntimeComponents(payload_encoder=interaction_encoder),
        client_components=RuntimeComponents(payload_encoder=client_encoder),
        sdk_defaults=_sdk(sdk_encoder),
    )
    client_selected = select_execution_components(
        mode,
        execution_plan,
        _resolved_plan(payload_encoders=(plan_encoder,)),
        interaction_components=None,
        client_components=RuntimeComponents(payload_encoder=client_encoder),
        sdk_defaults=_sdk(sdk_encoder),
    )
    plan_selected = select_execution_components(
        mode,
        execution_plan,
        _resolved_plan(payload_encoders=(plan_encoder,)),
        interaction_components=None,
        client_components=None,
        sdk_defaults=_sdk(sdk_encoder),
    )
    sdk_selected = select_execution_components(
        mode,
        execution_plan,
        _direct_plan(_Adapter("plan-adapter")),
        interaction_components=None,
        client_components=None,
        sdk_defaults=_sdk(sdk_encoder),
    )

    # Each call keeps the other layers populated so a fallback would be visible.
    assert _role(interaction_selected, "codec.request.encoder") is interaction_encoder
    assert _role(client_selected, "codec.request.encoder") is client_encoder
    assert _role(plan_selected, "codec.request.encoder") is plan_encoder
    assert _role(sdk_selected, "codec.request.encoder") is sdk_encoder


def test_missing_role_and_ambiguous_role_fail_independently() -> None:
    """Verify absence and same-layer ties use different stable errors."""
    missing = _capture(
        lambda: select_execution_components(
            _Mode(OpenIdentifier("unary")),
            _execution_plan(),
            _direct_plan(_Adapter("plan-adapter")),
            interaction_components=None,
            client_components=None,
            sdk_defaults=_sdk(include_transport=False),
        )
    )
    first = _Transport("plan-transport-a")
    second = _Transport("plan-transport-b")
    ambiguous = _capture(
        lambda: select_execution_components(
            _Mode(OpenIdentifier("unary")),
            _execution_plan(),
            _resolved_plan(transports=(first, second)),
            interaction_components=None,
            client_components=None,
            sdk_defaults=_sdk(include_transport=False),
        )
    )

    assert isinstance(missing, ModelInteractionError)
    assert missing.code == "component_not_found"
    assert isinstance(ambiguous, ModelInteractionError)
    assert ambiguous.code == "ambiguous_component_selection"
    assert missing.code != ambiguous.code


def test_incompatible_higher_layer_does_not_fall_back() -> None:
    """Verify a present layer with no role match hides the SDK component."""
    error = _capture(
        lambda: select_execution_components(
            _Mode(OpenIdentifier("unary")),
            _execution_plan(),
            _resolved_plan(payload_encoders=(_Transport("not-an-encoder"),)),
            interaction_components=None,
            client_components=None,
            sdk_defaults=_sdk(),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "component_not_found"


def _role(selection: ComponentSelectionResolution, role_id: str) -> object:
    """Return the component selected for one role identifier."""
    for selected in selection.components:
        if selected.role.id.value == role_id:
            return selected.component
    raise AssertionError(f"Missing selected role {role_id}.")


def test_out_of_scope_plan_fails_before_component_selection() -> None:
    """Verify a non-unary mode does not collapse into a component error."""
    error = _capture(
        lambda: select_execution_components(
            _Mode(OpenIdentifier("server_stream")),
            _execution_plan(),
            _resolved_plan(
                transports=(
                    _Transport("plan-transport-a"),
                    _Transport("plan-transport-b"),
                )
            ),
            interaction_components=None,
            client_components=None,
            sdk_defaults=_sdk(include_transport=False),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_interaction_mode"


def _resolved_plan(
    *,
    payload_encoders: tuple[_Encoder | _Transport, ...] = (),
    transports: tuple[_Transport, ...] = (),
) -> ModelIntegrationPlan:
    """Return a resolved plan with the requested binding candidates."""
    return ModelIntegrationPlan(
        source="resolved_binding",
        binding_id="vendor.binding",
        binding_version="1.0.0",
        match=ModelIntegrationMatch(ModelTargetMatch(True, 1), TaskMatch(True, 1)),
        task_protocol_adapter=_Adapter("plan-adapter"),
        payload_encoders=payload_encoders,
        transports=transports,
    )
