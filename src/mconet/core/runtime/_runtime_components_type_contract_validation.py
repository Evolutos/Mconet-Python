"""Type-contract validation for directly injected runtime components."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort
from mconet.core.spi.runtime_component import RuntimeComponent
from mconet.core.spi.runtime_components import RuntimeComponents

_INVALID_COMPONENT_CONFIGURATION = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_COMPONENT_TYPE_VALIDATION = InteractionPhase(
    OpenIdentifier("component_type_validation")
)
_INVALID_CONTRACT_CODE = "invalid_component_type_contract"
_INVALID_CONTRACT_MESSAGE = "Adjacent component type ports are incompatible."
_SUCCESS_INPUT_NAME = "response"
_ERROR_INPUT_NAME = "error"


def validate_runtime_components_type_contracts(
    components: RuntimeComponents,
) -> RuntimeComponents:
    """Fail when two injected neighbors declare incompatible data ports.

    Client creation only checks an edge whose two components are both present.
    An omitted encoder or decoder is not a mismatch; selection still checks the
    completed edge later. The request edge connects the adapter's single output
    to the encoder's single input. The success and error edges connect each
    decoder's single output to the adapter input named ``response`` or
    ``error``. Transport, resolvers, and handlers have no R1 data edge here.
    Behavior methods are not called.

    Args:
        components: One direct-injection carrier supplied at client creation.

    Returns:
        The same carrier when every present adjacent edge connects.

    Raises:
        TypeError: If the carrier or a present data component is not the
            expected nominal type.
        ModelInteractionError: If a present edge has a missing contract or
            incompatible ports. The code is ``invalid_component_type_contract``.
    """
    candidate = cast(object, components)
    if not isinstance(candidate, RuntimeComponents):
        raise TypeError("components must be a RuntimeComponents.")

    adapter = candidate.task_protocol_adapter
    encoder = candidate.payload_encoder
    success_decoder = candidate.success_payload_decoder
    error_decoder = candidate.error_payload_decoder

    # Read contracts only for edges that have both ends. A single injected
    # component cannot be adjacent to an SDK default that is not known yet.
    if adapter is not None and encoder is not None:
        _require_compatible(
            _single_port(_contract(adapter, "task_protocol_adapter").outputs),
            _single_port(_contract(encoder, "payload_encoder").inputs),
        )
    if adapter is not None and success_decoder is not None:
        _require_compatible(
            _single_port(_contract(success_decoder, "success_payload_decoder").outputs),
            _named_port(
                _contract(adapter, "task_protocol_adapter").inputs,
                _SUCCESS_INPUT_NAME,
            ),
        )
    if adapter is not None and error_decoder is not None:
        _require_compatible(
            _single_port(_contract(error_decoder, "error_payload_decoder").outputs),
            _named_port(
                _contract(adapter, "task_protocol_adapter").inputs,
                _ERROR_INPUT_NAME,
            ),
        )
    return candidate


def _contract(value: object, field_name: str) -> ComponentTypeContract:
    """Return the type contract of one present data component."""
    if not isinstance(value, RuntimeComponent):
        raise TypeError(f"{field_name} must implement RuntimeComponent.")
    descriptor = cast(object, value.descriptor)
    if not isinstance(descriptor, ComponentDescriptor):
        raise TypeError(f"{field_name} descriptor must be a ComponentDescriptor.")
    contract = descriptor.type_contract
    # A data role on a present edge must declare ports. None cannot prove that
    # the neighbor's port is the value this component accepts or produces.
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
    """Fail client creation unless both ports exist and agree."""
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
    # when both ports declare them, matching the selection-time connection rule.
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
