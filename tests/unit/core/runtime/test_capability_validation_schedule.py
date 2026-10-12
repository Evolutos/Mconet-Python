"""Tests for capability validation scheduled after type contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mconet.core.domain import (
    Extensions,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._capability_validation_schedule import (
    validate_selected_capabilities,
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


@dataclass(frozen=True, slots=True)
class _Requirement:
    """One collected capability requirement."""

    capability_id: OpenIdentifier
    required: bool
    constraints: Extensions
    source_path: str | None
    extensions: Extensions


class _Component:
    """Descriptor-only component used as a selected role."""

    def __init__(
        self,
        name: str,
        contract: ComponentTypeContract | None,
        capabilities: frozenset[OpenIdentifier],
    ) -> None:
        """Store the contract and capability identifiers validation reads."""
        self.descriptor = ComponentDescriptor(
            name,
            "1.0.0",
            "builtin",
            contract,
            capabilities,
        )


def _json_port(name: str, type_name: str = "json.value") -> ComponentTypePort:
    """Return one application/json port."""
    return ComponentTypePort(
        name,
        OpenIdentifier(type_name),
        None,
        MediaType("application", "json"),
    )


def _selection(
    capabilities: frozenset[OpenIdentifier],
    *,
    encoder_type: str = "json.value",
) -> ComponentSelectionResolution:
    """Return a unary selection, with capabilities declared on the transport."""
    adapter = ComponentTypeContract(
        inputs=(_json_port("response"), _json_port("error")),
        outputs=(_json_port("payload"),),
    )
    return ComponentSelectionResolution(
        (
            _selected("task.protocol-adapter", "adapter", adapter, frozenset()),
            _selected(
                "codec.request.encoder",
                "encoder",
                ComponentTypeContract(inputs=(_json_port("input", encoder_type),)),
                frozenset(),
            ),
            _selected(
                "codec.response.success-decoder",
                "success",
                ComponentTypeContract(outputs=(_json_port("output"),)),
                frozenset(),
            ),
            _selected(
                "codec.response.error-decoder",
                "error",
                ComponentTypeContract(outputs=(_json_port("output"),)),
                frozenset(),
            ),
            _selected("transport.unary", "transport", None, capabilities),
        )
    )


def _selected(
    role_id: str,
    name: str,
    contract: ComponentTypeContract | None,
    capabilities: frozenset[OpenIdentifier],
) -> SelectedComponent:
    """Bind one role to a component and the same descriptor snapshot."""
    component = _Component(name, contract, capabilities)
    return SelectedComponent(
        ComponentRole(OpenIdentifier(role_id)),
        component,
        component.descriptor,
    )


def _requirement(capability_id: str, *, required: bool) -> _Requirement:
    """Return one requirement with no constraints."""
    return _Requirement(
        OpenIdentifier(capability_id),
        required,
        {},
        "interaction.mode",
        {},
    )


def test_required_absence_fails_and_optional_absence_is_only_a_diagnostic() -> None:
    """Verify the two capability outcomes stay independent."""
    text = OpenIdentifier("model.input.text")
    selection = _selection(frozenset((text,)))
    later: list[str] = []
    missing = _capture(
        lambda: (
            validate_selected_capabilities(
                selection,
                (_requirement("model.input.image", required=True),),
            ),
            later.append("continued"),
        )
    )
    resolved = validate_selected_capabilities(
        selection,
        (
            _requirement("model.input.text", required=True),
            _requirement("model.input.image", required=False),
        ),
    )

    assert isinstance(missing, ModelInteractionError)
    assert missing.code == "unsupported_capability"
    assert later == []
    assert len(resolved.satisfied) == 1
    assert resolved.satisfied[0].requirement.capability_id == text
    assert len(resolved.diagnostics) == 1
    assert resolved.diagnostics[0].code == "optional_capability_unsupported"
    assert resolved.optional_unsupported[0].required is False


def test_type_contract_failure_stops_before_capability_resolution() -> None:
    """Verify a broken port is not reported as a missing capability."""
    error = _capture(
        lambda: validate_selected_capabilities(
            _selection(frozenset(), encoder_type="grpc.message"),
            (_requirement("model.input.text", required=True),),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_component_type_contract"
