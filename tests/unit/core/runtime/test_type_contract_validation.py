"""Tests for adjacent component type-contract validation."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import MediaType, ModelInteractionError, OpenIdentifier
from mconet.core.runtime._type_contract_validation import (
    validate_selected_type_contracts,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentRole,
    ComponentSelectionResolution,
    ComponentTypeContract,
    ComponentTypePort,
    SelectedComponent,
)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


class _Component:
    """Descriptor-only component used as a selected data role."""

    def __init__(self, name: str, contract: ComponentTypeContract | None) -> None:
        """Store the contract that validation will read."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application", contract)


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


def _selection(
    *,
    adapter_outputs: tuple[ComponentTypePort, ...] | None = None,
    adapter_inputs: tuple[ComponentTypePort, ...] | None = None,
    encoder_inputs: tuple[ComponentTypePort, ...] | None = None,
    success_outputs: tuple[ComponentTypePort, ...] | None = None,
    error_outputs: tuple[ComponentTypePort, ...] | None = None,
    include_encoder_contract: bool = True,
) -> ComponentSelectionResolution:
    """Build a selection whose unset ports use the connecting R1 contracts."""
    outputs = (
        (_port("payload", schema_id="openai.chat"),)
        if adapter_outputs is None
        else adapter_outputs
    )
    inputs = (
        (_port("response"), _port("error"))
        if adapter_inputs is None
        else adapter_inputs
    )
    encoded = (_port("input"),) if encoder_inputs is None else encoder_inputs
    success = (_port("output"),) if success_outputs is None else success_outputs
    error = (_port("output"),) if error_outputs is None else error_outputs
    encoder = (
        ComponentTypeContract(inputs=encoded) if include_encoder_contract else None
    )
    return ComponentSelectionResolution(
        (
            _selected(
                "task.protocol-adapter",
                "adapter",
                ComponentTypeContract(inputs=inputs, outputs=outputs),
            ),
            _selected("codec.request.encoder", "encoder", encoder),
            _selected(
                "codec.response.success-decoder",
                "success",
                ComponentTypeContract(outputs=success),
            ),
            _selected(
                "codec.response.error-decoder",
                "error",
                ComponentTypeContract(outputs=error),
            ),
            _selected("transport.unary", "transport", None),
        )
    )


def _selected(
    role_id: str,
    name: str,
    contract: ComponentTypeContract | None,
) -> SelectedComponent:
    """Bind one role to a component and the same descriptor snapshot."""
    component = _Component(name, contract)
    return SelectedComponent(
        ComponentRole(OpenIdentifier(role_id)),
        component,
        component.descriptor,
    )


def test_compatible_json_ports_keep_the_same_selection() -> None:
    """Verify omitted encoder schema still connects to a schema-bearing payload."""
    selection = _selection()

    assert validate_selected_type_contracts(selection) is selection


def test_each_broken_edge_fails_before_a_later_stage() -> None:
    """Verify request, success, and error mismatches share one stable failure."""
    later: list[str] = []
    cases = (
        _selection(encoder_inputs=(_port("input", "grpc.message"),)),
        _selection(
            success_outputs=(_port("output", media_type=MediaType("text", "plain")),)
        ),
        _selection(
            adapter_inputs=(
                _port("response"),
                _port("error", schema_id="openai.error"),
            ),
            error_outputs=(_port("output", schema_id="other.schema"),),
        ),
        _selection(adapter_inputs=(_port("error"),)),
        _selection(include_encoder_contract=False),
    )

    for selection in cases:
        error = _capture(
            lambda selection=selection: (
                validate_selected_type_contracts(selection),
                later.append("continued"),
            )
        )
        assert isinstance(error, ModelInteractionError)
        assert error.code == "invalid_component_type_contract"
        assert error.phase.id.value == "component_type_validation"

    assert later == []
