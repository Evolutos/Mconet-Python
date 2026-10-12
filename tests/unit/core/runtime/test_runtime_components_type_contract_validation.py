"""Type-contract validation for directly injected runtime components."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain import MediaType, ModelInteractionError, OpenIdentifier
from mconet.core.runtime._runtime_components_type_contract_validation import (
    validate_runtime_components_type_contracts,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    PayloadDecoder,
    PayloadEncoder,
    RuntimeComponents,
    TaskProtocolAdapter,
    Transport,
)

_DEFAULT_CONTRACT = object()


class _Component:
    """Descriptor carrier whose behavior must stay idle during validation."""

    def __init__(self, name: str, contract: ComponentTypeContract | None) -> None:
        """Store the contract that client creation will read."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application", contract)
        self.calls: list[str] = []

    def encode(self, payload: object) -> object:
        """Record an encode call that validation must not make."""
        del payload
        self.calls.append("encode")
        return None


def _port(
    name: str,
    type_name: str = "json.value",
    *,
    schema_id: str | None = None,
    media_type: MediaType | None = None,
) -> ComponentTypePort:
    """Build one port, defaulting its media type to application/json."""
    media = MediaType("application", "json") if media_type is None else media_type
    return ComponentTypePort(name, OpenIdentifier(type_name), schema_id, media)


def _adapter(
    *,
    output_type: str = "json.value",
    output_schema: str | None = "openai.chat",
    response_type: str = "json.value",
    error_type: str = "json.value",
    contract: ComponentTypeContract | None = None,
) -> _Component:
    """Build an adapter whose ports connect to the default encoder and decoders."""
    if contract is None:
        contract = ComponentTypeContract(
            inputs=(_port("response", response_type), _port("error", error_type)),
            outputs=(_port("payload", output_type, schema_id=output_schema),),
        )
    return _Component("adapter", contract)


def _encoder(
    *,
    input_type: str = "json.value",
    schema_id: str | None = "openai.chat",
    media_type: MediaType | None = None,
    contract: ComponentTypeContract | object | None = _DEFAULT_CONTRACT,
) -> _Component:
    """Build an encoder with one input port, or with no contract when asked."""
    if contract is _DEFAULT_CONTRACT:
        contract = ComponentTypeContract(
            inputs=(
                _port(
                    "input",
                    input_type,
                    schema_id=schema_id,
                    media_type=media_type,
                ),
            )
        )
    return _Component("encoder", cast(ComponentTypeContract | None, contract))


def _decoder(name: str, *, output_type: str = "json.value") -> _Component:
    """Build a decoder with one output port."""
    return _Component(
        name,
        ComponentTypeContract(outputs=(_port("output", output_type),)),
    )


def _expect(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _assert_contract_error(error: BaseException) -> None:
    """Require the stable type-contract failure without port details."""
    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_component_type_contract"
    assert str(error.phase.id) == "component_type_validation"
    assert str(error.category.id) == "invalid_component_configuration"
    assert "json.value" not in error.message
    assert "payload" not in error.message


def test_empty_components_keep_their_identity() -> None:
    """Accept a carrier that injects no adjacent data components."""
    components = RuntimeComponents()
    assert validate_runtime_components_type_contracts(components) is components


def test_a_single_injected_encoder_has_no_adjacent_edge() -> None:
    """Leave an encoder unchecked until its adapter neighbor is also injected."""
    encoder = _encoder(input_type="transport.bytes", contract=None)
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, encoder))
    assert validate_runtime_components_type_contracts(components) is components
    assert encoder.calls == []


def test_connecting_injected_ports_are_accepted_without_calls() -> None:
    """Accept adapter, encoder, and both decoders when every edge connects."""
    adapter = _adapter()
    encoder = _encoder()
    success = _decoder("success")
    error = _decoder("error")
    transport = _Component("transport", None)
    components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        payload_encoder=cast(PayloadEncoder, encoder),
        success_payload_decoder=cast(PayloadDecoder, success),
        error_payload_decoder=cast(PayloadDecoder, error),
        transport=cast(Transport, transport),
    )
    assert validate_runtime_components_type_contracts(components) is components
    assert adapter.calls == encoder.calls == success.calls == error.calls == []


def test_request_edge_type_mismatch_fails_at_client_creation() -> None:
    """Reject an injected adapter and encoder whose types do not connect."""
    adapter = _adapter()
    encoder = _encoder(input_type="transport.bytes")
    components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
        payload_encoder=cast(PayloadEncoder, encoder),
    )
    error = _expect(
        ModelInteractionError,
        lambda: validate_runtime_components_type_contracts(components),
        "Adjacent component type ports are incompatible.",
    )
    _assert_contract_error(error)
    assert adapter.calls == encoder.calls == []


def test_success_and_error_edges_fail_independently() -> None:
    """Reject each decoder edge without requiring the other decoder."""
    success_components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        success_payload_decoder=cast(
            PayloadDecoder, _decoder("success", output_type="text.value")
        ),
    )
    error_components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        error_payload_decoder=cast(
            PayloadDecoder, _decoder("error", output_type="text.value")
        ),
    )
    _assert_contract_error(
        _expect(
            ModelInteractionError,
            lambda: validate_runtime_components_type_contracts(success_components),
            "Adjacent component type ports are incompatible.",
        )
    )
    _assert_contract_error(
        _expect(
            ModelInteractionError,
            lambda: validate_runtime_components_type_contracts(error_components),
            "Adjacent component type ports are incompatible.",
        )
    )


def test_schema_and_media_constrain_only_when_both_sides_declare_them() -> None:
    """Accept an omitted schema and reject two declared values that differ."""
    omitted = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        payload_encoder=cast(PayloadEncoder, _encoder(schema_id=None)),
    )
    assert validate_runtime_components_type_contracts(omitted) is omitted

    schema_mismatch = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        payload_encoder=cast(PayloadEncoder, _encoder(schema_id="other.chat")),
    )
    _assert_contract_error(
        _expect(
            ModelInteractionError,
            lambda: validate_runtime_components_type_contracts(schema_mismatch),
            "Adjacent component type ports are incompatible.",
        )
    )

    mismatched = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        payload_encoder=cast(
            PayloadEncoder,
            _encoder(media_type=MediaType("text", "plain")),
        ),
    )
    _assert_contract_error(
        _expect(
            ModelInteractionError,
            lambda: validate_runtime_components_type_contracts(mismatched),
            "Adjacent component type ports are incompatible.",
        )
    )


def test_missing_contract_on_a_present_edge_fails() -> None:
    """Reject a neighbor that declares no ports for an injected edge."""
    components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        payload_encoder=cast(PayloadEncoder, _encoder(contract=None)),
    )
    _assert_contract_error(
        _expect(
            ModelInteractionError,
            lambda: validate_runtime_components_type_contracts(components),
            "Adjacent component type ports are incompatible.",
        )
    )


def test_present_edge_requires_a_runtime_component() -> None:
    """Reject a neighbor that cannot expose a type contract."""
    components = RuntimeComponents(
        task_protocol_adapter=cast(TaskProtocolAdapter, _adapter()),
        payload_encoder=cast(PayloadEncoder, object()),
    )
    _expect(
        TypeError,
        lambda: validate_runtime_components_type_contracts(components),
        "payload_encoder must implement RuntimeComponent",
    )


def test_non_carrier_is_rejected_before_port_checks() -> None:
    """Reject a value that is not a runtime component carrier."""
    _expect(
        TypeError,
        lambda: validate_runtime_components_type_contracts(
            cast(RuntimeComponents, object())
        ),
        "components must be a RuntimeComponents",
    )
