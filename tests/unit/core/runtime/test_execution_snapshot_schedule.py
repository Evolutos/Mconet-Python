"""Tests for freezing an interaction execution snapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._execution_snapshot_schedule import (
    freeze_interaction_execution_components,
)
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    ComponentDescriptor,
    ComponentRole,
    ComponentSelectionResolution,
    ComponentTypeContract,
    ComponentTypePort,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    RuntimeComponent,
    SelectedComponent,
    ServiceAccessResolver,
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


@dataclass(slots=True)
class _Executable:
    """Behavior component that snapshot construction must not call."""

    descriptor: ComponentDescriptor
    calls: list[str] = field(default_factory=list[str])

    def _forbid(self, method: str) -> None:
        """Record and reject one behavior call."""
        self.calls.append(method)
        raise AssertionError(f"Snapshot scheduling invoked {method}.")

    def supports(self, *values: object) -> object:
        """Reject adapter applicability during snapshot construction."""
        del values
        self._forbid("supports")

    def prepare_plan(self, *values: object) -> object:
        """Reject planning during snapshot construction."""
        del values
        self._forbid("prepare_plan")

    def build_request(self, *values: object) -> object:
        """Reject request mapping during snapshot construction."""
        del values
        self._forbid("build_request")

    def parse_response(self, *values: object) -> object:
        """Reject response parsing during snapshot construction."""
        del values
        self._forbid("parse_response")

    def parse_error(self, *values: object) -> object:
        """Reject error parsing during snapshot construction."""
        del values
        self._forbid("parse_error")

    def encode(self, *values: object) -> object:
        """Reject encoding during snapshot construction."""
        del values
        self._forbid("encode")

    def decode(self, *values: object) -> object:
        """Reject decoding during snapshot construction."""
        del values
        self._forbid("decode")

    async def send(self, *values: object) -> object:
        """Reject transport I/O during snapshot construction."""
        del values
        self._forbid("send")

    def resolve(self, *values: object) -> object:
        """Reject resolver execution during snapshot construction."""
        del values
        self._forbid("resolve")

    async def apply(self, *values: object) -> None:
        """Reject authorization during snapshot construction."""
        del values
        self._forbid("apply")


def _port(name: str, type_name: str = "json.value") -> ComponentTypePort:
    """Return one application/json port."""
    return ComponentTypePort(
        name,
        OpenIdentifier(type_name),
        None,
        MediaType("application", "json"),
    )


def _component(
    name: str,
    contract: ComponentTypeContract | None,
) -> _Executable:
    """Return one component with the given contract."""
    return _Executable(ComponentDescriptor(name, "1.0.0", "application", contract))


def _graph(
    encoder_type: str = "json.value",
) -> tuple[ModelIntegrationPlan, ComponentSelectionResolution, _Executable]:
    """Return a direct plan, its selection, and the selected encoder."""
    adapter = _component(
        "adapter",
        ComponentTypeContract(
            inputs=(_port("response"), _port("error")),
            outputs=(_port("payload"),),
        ),
    )
    encoder = _component(
        "encoder",
        ComponentTypeContract(inputs=(_port("input", encoder_type),)),
    )
    success = _component(
        "success",
        ComponentTypeContract(outputs=(_port("output"),)),
    )
    error = _component("error", ComponentTypeContract(outputs=(_port("output"),)))
    transport = _component("transport", ComponentTypeContract())
    selected = (
        ("task.protocol-adapter", adapter),
        ("codec.request.encoder", encoder),
        ("codec.response.success-decoder", success),
        ("codec.response.error-decoder", error),
        ("transport.unary", transport),
    )
    selection = ComponentSelectionResolution(
        tuple(
            SelectedComponent(
                ComponentRole(OpenIdentifier(role_id)),
                component,
                component.descriptor,
            )
            for role_id, component in selected
        )
    )
    plan = ModelIntegrationPlan("direct_adapter", None, None, None, adapter)
    return plan, selection, encoder


def _freeze(
    plan: ModelIntegrationPlan,
    selection: ComponentSelectionResolution,
    requirements: tuple[_Requirement, ...] = (),
) -> InteractionExecutionComponents:
    """Freeze one snapshot from the shared completed inputs."""
    access = _component("access", None)
    authorization = _component("authorization-resolver", None)
    return freeze_interaction_execution_components(
        integration_plan=plan,
        component_selection=selection,
        resource_limits=ResolvedInteractionResourceLimits(4_096, 1_024, 512),
        service_access_resolver=cast(ServiceAccessResolver, access),
        authorization_handler_resolver=cast(
            AuthorizationHandlerResolver, authorization
        ),
        authorization_handlers=cast(
            tuple[AuthorizationHandler, ...],
            (_component("handler", None),),
        ),
        requirements=requirements,
    )


def test_snapshot_keeps_selected_instances_and_rejects_replacement() -> None:
    """Verify the frozen snapshot does not follow a later caller replacement."""
    plan, selection, encoder = _graph()
    caller_components: list[RuntimeComponent] = [encoder]
    snapshot = _freeze(plan, selection)
    replacement = _component("replacement", ComponentTypeContract())
    caller_components[0] = replacement
    error = _capture(lambda: setattr(snapshot, "payload_encoder", replacement))

    assert snapshot.payload_encoder is encoder
    assert snapshot.payload_encoder is not replacement
    assert isinstance(error, FrozenInstanceError)
    assert encoder.calls == []


def test_type_and_capability_failures_do_not_freeze_a_snapshot() -> None:
    """Verify either earlier gate stops before snapshot construction."""
    broken_plan, broken_selection, _encoder = _graph("grpc.message")
    valid_plan, valid_selection, _valid_encoder = _graph()
    type_error = _capture(lambda: _freeze(broken_plan, broken_selection))
    capability_error = _capture(
        lambda: _freeze(
            valid_plan,
            valid_selection,
            (
                _Requirement(
                    OpenIdentifier("model.input.image"),
                    True,
                    {},
                    None,
                    {},
                ),
            ),
        )
    )

    assert isinstance(type_error, ModelInteractionError)
    assert type_error.code == "invalid_component_type_contract"
    assert isinstance(capability_error, ModelInteractionError)
    assert capability_error.code == "unsupported_capability"
