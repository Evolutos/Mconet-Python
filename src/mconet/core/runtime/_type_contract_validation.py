"""Runtime scheduling for adjacent component type-contract checks."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.component_selection_resolution import ComponentSelectionResolution
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort
from mconet.core.spi.runtime_component import RuntimeComponent

_INVALID_COMPONENT_CONFIGURATION = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_COMPONENT_TYPE_VALIDATION = InteractionPhase(
    OpenIdentifier("component_type_validation")
)
_INVALID_CONTRACT_CODE = "invalid_component_type_contract"
_INVALID_CONTRACT_MESSAGE = "Adjacent component type ports are incompatible."
_ADAPTER_ROLE = "task.protocol-adapter"
_ENCODER_ROLE = "codec.request.encoder"
_SUCCESS_DECODER_ROLE = "codec.response.success-decoder"
_ERROR_DECODER_ROLE = "codec.response.error-decoder"
_SUCCESS_INPUT_NAME = "response"
_ERROR_INPUT_NAME = "error"


def validate_selected_type_contracts(
    selection: ComponentSelectionResolution,
) -> ComponentSelectionResolution:
    """Reject a selection whose adjacent data ports do not connect.

    The request edge connects the adapter's single payload output to the
    encoder's single input. The success edge connects the success decoder's
    single output to the adapter input named ``response``. The error edge
    connects the error decoder's single output to the adapter input named
    ``error``. A port matches when its type identifier is equal and any schema
    or media type declared on both sides is equal. The first broken edge fails
    the interaction. Transport has no JSON port in the R1 contracts, so this
    gate does not invent a byte connection for it.

    Args:
        selection: Unique components already chosen for this interaction.

    Returns:
        The same selection when every data edge connects.

    Raises:
        TypeError: If ``selection`` is not a ComponentSelectionResolution.
        ModelInteractionError: If a required data role, contract, or adjacent
            port is missing or incompatible. The code is
            ``invalid_component_type_contract``.
    """
    selection_value = cast(object, selection)
    if not isinstance(selection_value, ComponentSelectionResolution):
        raise TypeError("selection must be a ComponentSelectionResolution.")

    adapter = _required_component(selection_value, _ADAPTER_ROLE)
    encoder = _required_component(selection_value, _ENCODER_ROLE)
    success_decoder = _required_component(selection_value, _SUCCESS_DECODER_ROLE)
    error_decoder = _required_component(selection_value, _ERROR_DECODER_ROLE)
    adapter_contract = _required_contract(adapter)
    encoder_contract = _required_contract(encoder)
    success_contract = _required_contract(success_decoder)
    error_contract = _required_contract(error_decoder)

    # Request bytes are not a JSON port. Only the payload value crosses this
    # edge, so one output and one input are the whole connection.
    _require_compatible(
        _single_port(adapter_contract.outputs),
        _single_port(encoder_contract.inputs),
    )
    # Two adapter inputs stay distinct. A success payload must not satisfy the
    # check merely because the error input happens to use the same type.
    _require_compatible(
        _single_port(success_contract.outputs),
        _named_port(adapter_contract.inputs, _SUCCESS_INPUT_NAME),
    )
    _require_compatible(
        _single_port(error_contract.outputs),
        _named_port(adapter_contract.inputs, _ERROR_INPUT_NAME),
    )
    return selection_value


def _required_component(
    selection: ComponentSelectionResolution,
    role_id: str,
) -> RuntimeComponent:
    """Return the one component stored for a data-bearing role."""
    matches = [
        selected.component
        for selected in selection.components
        if selected.role.id.value == role_id
    ]
    # Selection already forbids duplicate roles. Absence still cannot continue,
    # because an unwired edge would otherwise reach encoding.
    if len(matches) != 1:
        raise _contract_error()
    return matches[0]


def _required_contract(component: RuntimeComponent) -> ComponentTypeContract:
    """Return the contract a data-bearing component must already declare."""
    contract = component.descriptor.type_contract
    # None is valid for a component with no ports. These four roles exchange
    # values, so a missing contract cannot prove an adjacent connection.
    if contract is None:
        raise _contract_error()
    return contract


def _single_port(
    ports: tuple[ComponentTypePort, ...],
) -> ComponentTypePort | None:
    """Return the only port in a direction, or none when the count is not one."""
    if len(ports) != 1:
        return None
    return ports[0]


def _named_port(
    ports: tuple[ComponentTypePort, ...],
    name: str,
) -> ComponentTypePort | None:
    """Return the one port with this name, or none when the name is not unique."""
    matches = [port for port in ports if port.name == name]
    if len(matches) != 1:
        return None
    return matches[0]


def _require_compatible(
    output_port: ComponentTypePort | None,
    input_port: ComponentTypePort | None,
) -> None:
    """Fail the interaction unless both ports exist and agree."""
    if (
        output_port is None
        or input_port is None
        or not _ports_compatible(output_port, input_port)
    ):
        raise _contract_error()


def _ports_compatible(
    output_port: ComponentTypePort,
    input_port: ComponentTypePort,
) -> bool:
    """Return whether one output can feed one input."""
    # Type identity is mandatory. Schema and media type constrain the edge only
    # when both ports declare them, so an omitted schema can still meet a
    # protocol-specific schema.
    if output_port.type_id != input_port.type_id:
        return False
    if (
        output_port.schema_id is not None
        and input_port.schema_id is not None
        and output_port.schema_id != input_port.schema_id
    ):
        return False
    return (
        output_port.media_type is None
        or input_port.media_type is None
        or output_port.media_type == input_port.media_type
    )


def _contract_error() -> ModelInteractionError:
    """Create the stable failure for one broken type-contract edge."""
    # The message excludes port names, type identifiers, and component metadata
    # so a contract fact cannot become log content.
    return ModelInteractionError(
        category=_INVALID_COMPONENT_CONFIGURATION,
        phase=_COMPONENT_TYPE_VALIDATION,
        code=_INVALID_CONTRACT_CODE,
        message=_INVALID_CONTRACT_MESSAGE,
    )
