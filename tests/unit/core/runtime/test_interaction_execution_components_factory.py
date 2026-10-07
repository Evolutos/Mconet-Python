"""Tests for unary interaction execution-component snapshot construction."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import OpenIdentifier, ResolvedInteractionResourceLimits
from mconet.core.runtime._interaction_execution_components_factory import (
    create_interaction_execution_components,
)
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentRole,
    ComponentSelectionResolution,
    ComponentTypeContract,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    RuntimeComponent,
    SelectedComponent,
    ServiceAccessResolver,
)

_ROLE_IDS = (
    "task.protocol-adapter",
    "codec.request.encoder",
    "codec.response.success-decoder",
    "codec.response.error-decoder",
    "transport.unary",
)


@dataclass(slots=True)
class _ExecutableComponent:
    """Complete multi-role behavior fixture that must never be invoked."""

    descriptor: ComponentDescriptor
    """Nominal metadata inspected by selection and factory validation."""

    calls: list[str] = field(default_factory=list[str])
    """Behavior-call evidence retained independently for each fixture."""

    def _forbid(self, method: str) -> None:
        """Record and reject one unexpected component behavior invocation."""
        # The factory may inspect protocol members but must not call any behavior
        # while constructing a passive immutable execution snapshot.
        self.calls.append(method)
        raise AssertionError(f"Factory unexpectedly invoked {method}.")

    def supports(self, *values: object) -> object:
        """Reject adapter or authorization applicability execution."""
        # Accept generic fixture inputs so one object can structurally model each
        # tested protocol without duplicating behavior that must stay uncalled.
        del values
        self._forbid("supports")

    def prepare_plan(self, *values: object) -> object:
        """Reject protocol planning during snapshot construction."""
        # Planning was completed before factory invocation and cannot be repeated.
        del values
        self._forbid("prepare_plan")

    def build_request(self, *values: object) -> object:
        """Reject request mapping during snapshot construction."""
        # Request creation belongs to the later execution pipeline.
        del values
        self._forbid("build_request")

    def parse_response(self, *values: object) -> object:
        """Reject successful response parsing during snapshot construction."""
        # No response exists while immutable component ownership is being fixed.
        del values
        self._forbid("parse_response")

    def parse_error(self, *values: object) -> object:
        """Reject service-error parsing during snapshot construction."""
        # Error parsing remains unreachable before transport execution.
        del values
        self._forbid("parse_error")

    def encode(self, *values: object) -> object:
        """Reject payload encoding during snapshot construction."""
        # The factory retains the encoder instance without observing payloads.
        del values
        self._forbid("encode")

    def decode(self, *values: object) -> object:
        """Reject payload decoding during snapshot construction."""
        # Both response decoders are fixed before any response bytes exist.
        del values
        self._forbid("decode")

    async def send(self, *values: object) -> object:
        """Reject transport I/O during snapshot construction."""
        # Async behavior presence satisfies structural Transport conformance, but
        # no coroutine can be created or awaited at this pure construction step.
        del values
        self._forbid("send")

    def resolve(self, *values: object) -> object:
        """Reject service-access or authorization resolution execution."""
        # Both resolver instances are retained as behavior, not invoked by factory.
        del values
        self._forbid("resolve")

    async def apply(self, *values: object) -> None:
        """Reject authorization mutation during snapshot construction."""
        # Authorization runs only after encoding and credential acquisition.
        del values
        self._forbid("apply")


@dataclass(frozen=True, slots=True)
class _DescriptorOnlyComponent:
    """Metadata-only component used to reject absent executable behavior."""

    descriptor: ComponentDescriptor
    """Valid metadata that cannot substitute for a role behavior protocol."""


@dataclass(frozen=True, slots=True)
class _FactoryFixture:
    """Collect one complete set of already-resolved factory inputs."""

    integration_plan: ModelIntegrationPlan
    """Completed integration provenance and candidate snapshot."""

    component_selection: ComponentSelectionResolution
    """Role-unique selected executable component facts."""

    resource_limits: ResolvedInteractionResourceLimits
    """Semantically validated finite limits for the interaction."""

    service_access_resolver: _ExecutableComponent
    """Input-dispatched access resolver retained outside ComponentRole."""

    authorization_handler_resolver: _ExecutableComponent
    """Input-dispatched authorization resolver retained outside ComponentRole."""

    authorization_handlers: tuple[_ExecutableComponent, ...]
    """Immutable ordered authorization handler candidates."""

    capability_resolution: CapabilityResolution
    """Completed required and optional capability facts."""

    selected_components: tuple[_ExecutableComponent, ...]
    """Expected role instances retained only for identity assertions."""


def _component(name: str, *, has_type_contract: bool = True) -> _ExecutableComponent:
    """Create one distinguishable non-invoked executable component fixture."""
    # A non-null empty contract exercises the factory's minimum completeness
    # guard; port compatibility remains the responsibility of its prior validator.
    type_contract = ComponentTypeContract() if has_type_contract else None
    return _ExecutableComponent(
        ComponentDescriptor(name, "1", "application", type_contract)
    )


def _selected(role_id: str, component: RuntimeComponent) -> SelectedComponent:
    """Bind one exact fixture instance to a validated open execution role."""
    # Snapshot the component's own nominal descriptor so SelectedComponent proves
    # metadata coherence before the factory inspects behavior or type contracts.
    return SelectedComponent(
        ComponentRole(OpenIdentifier(role_id)),
        component,
        component.descriptor,
    )


def _selection(
    components: tuple[RuntimeComponent, ...],
    role_ids: tuple[str, ...] = _ROLE_IDS,
) -> ComponentSelectionResolution:
    """Build one role-unique immutable selection in caller-controlled order."""
    # Zip strictness prevents a malformed test helper from silently omitting an
    # intended role or component before production validation is exercised.
    selected = tuple(
        _selected(role_id, component)
        for role_id, component in zip(role_ids, components, strict=True)
    )
    return ComponentSelectionResolution(selected)


def _direct_plan(component: RuntimeComponent) -> ModelIntegrationPlan:
    """Create one completed direct integration plan for an exact adapter object."""
    # A direct plan contains no binding candidates or defaults, so its adapter is
    # the only component fact that must converge with the later role selection.
    return ModelIntegrationPlan(
        "direct_adapter",
        None,
        None,
        None,
        component,
    )


def _fixture() -> _FactoryFixture:
    """Build complete unary selections, candidates, and resolved values."""
    selected_components = tuple(
        _component(f"selected:{role_id}") for role_id in _ROLE_IDS
    )
    adapter = selected_components[0]
    access_resolver = _component("service-access-resolver", has_type_contract=False)
    authorization_resolver = _component(
        "authorization-handler-resolver",
        has_type_contract=False,
    )
    handlers = (
        _component("authorization-handler:first", has_type_contract=False),
        _component("authorization-handler:second", has_type_contract=False),
    )

    # The direct plan and all aggregate inputs are completed nominal values. The
    # plan points at the same adapter instance without granting factory a fallback.
    return _FactoryFixture(
        integration_plan=_direct_plan(cast(RuntimeComponent, adapter)),
        component_selection=_selection(
            cast(tuple[RuntimeComponent, ...], selected_components)
        ),
        resource_limits=ResolvedInteractionResourceLimits(4_096, 1_024, 512),
        service_access_resolver=access_resolver,
        authorization_handler_resolver=authorization_resolver,
        authorization_handlers=handlers,
        capability_resolution=CapabilityResolution(),
        selected_components=selected_components,
    )


def _create(fixture: _FactoryFixture) -> InteractionExecutionComponents:
    """Invoke the factory with every complete fixture input explicitly."""
    # Explicit keyword mapping mirrors production orchestration and makes missing
    # completed stages visible at the call site instead of hiding them in a bag.
    return create_interaction_execution_components(
        integration_plan=fixture.integration_plan,
        component_selection=fixture.component_selection,
        resource_limits=fixture.resource_limits,
        service_access_resolver=cast(
            ServiceAccessResolver,
            fixture.service_access_resolver,
        ),
        authorization_handler_resolver=cast(
            AuthorizationHandlerResolver,
            fixture.authorization_handler_resolver,
        ),
        authorization_handlers=cast(
            tuple[AuthorizationHandler, ...],
            fixture.authorization_handlers,
        ),
        capability_resolution=fixture.capability_resolution,
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require one factory call to fail through the intended validation branch."""
    try:
        action()
    except exception_type as error:
        # A stable fragment distinguishes the target invariant from incidental
        # constructor or structural protocol failures in the fixtures.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_factory_derives_exact_selected_components_and_preserves_inputs() -> None:
    """Retain completed aggregates, candidates, and role-selected instances."""
    fixture = _fixture()

    result = _create(fixture)

    # Role lookup, rather than a parallel component argument, supplies every
    # executable field while all aggregate and candidate identities remain exact.
    assert result.integration_plan is fixture.integration_plan
    assert result.component_selection is fixture.component_selection
    assert result.resource_limits is fixture.resource_limits
    assert result.task_protocol_adapter is fixture.selected_components[0]
    assert result.payload_encoder is fixture.selected_components[1]
    assert result.success_payload_decoder is fixture.selected_components[2]
    assert result.error_payload_decoder is fixture.selected_components[3]
    assert result.transport is fixture.selected_components[4]
    assert result.service_access_resolver is fixture.service_access_resolver
    assert (
        result.authorization_handler_resolver is fixture.authorization_handler_resolver
    )
    assert result.authorization_handlers is fixture.authorization_handlers
    assert result.capability_resolution is fixture.capability_resolution


def test_factory_uses_roles_instead_of_selection_tuple_order() -> None:
    """Derive each execution field by fixed role when selection order changes."""
    fixture = _fixture()
    reversed_components = tuple(reversed(fixture.selected_components))
    reversed_roles = tuple(reversed(_ROLE_IDS))
    selection = _selection(
        cast(tuple[RuntimeComponent, ...], reversed_components),
        reversed_roles,
    )
    changed = _FactoryFixture(
        fixture.integration_plan,
        selection,
        fixture.resource_limits,
        fixture.service_access_resolver,
        fixture.authorization_handler_resolver,
        fixture.authorization_handlers,
        fixture.capability_resolution,
        fixture.selected_components,
    )

    result = _create(changed)

    # Every field still points at its original role component, proving tuple order
    # cannot become an undocumented positional wiring contract.
    assert result.task_protocol_adapter is fixture.selected_components[0]
    assert result.payload_encoder is fixture.selected_components[1]
    assert result.success_payload_decoder is fixture.selected_components[2]
    assert result.error_payload_decoder is fixture.selected_components[3]
    assert result.transport is fixture.selected_components[4]


def test_factory_requires_plan_and_selection_to_share_exact_adapter() -> None:
    """Reject a selected adapter instance that diverges from integration planning."""
    fixture = _fixture()
    replacement_adapter = _component("selected:replacement-adapter")
    components = (replacement_adapter, *fixture.selected_components[1:])
    changed = _FactoryFixture(
        fixture.integration_plan,
        _selection(cast(tuple[RuntimeComponent, ...], components)),
        fixture.resource_limits,
        fixture.service_access_resolver,
        fixture.authorization_handler_resolver,
        fixture.authorization_handlers,
        fixture.capability_resolution,
        components,
    )

    _assert_raises(
        ValueError,
        lambda: _create(changed),
        "selected task_protocol_adapter must match the integration plan",
    )

    # Neither adapter behavior is consulted to reconcile the contradiction; the
    # completed planning and selection facts must already agree by identity.
    assert fixture.selected_components[0].calls == []
    assert replacement_adapter.calls == []


def test_factory_invokes_no_component_behavior() -> None:
    """Construct a complete snapshot without planning, resolving, codec, or I/O calls."""
    fixture = _fixture()

    _create(fixture)

    # Include selected roles, both resolvers, and all authorization candidates so
    # every retained behavior boundary proves pure construction independently.
    all_components = (
        *fixture.selected_components,
        fixture.service_access_resolver,
        fixture.authorization_handler_resolver,
        *fixture.authorization_handlers,
    )
    assert all(component.calls == [] for component in all_components)


def test_factory_requires_exact_complete_unary_role_set() -> None:
    """Reject both an incomplete selection and a silently lossy extra role."""
    fixture = _fixture()
    missing = _selection(
        cast(tuple[RuntimeComponent, ...], fixture.selected_components[:-1]),
        _ROLE_IDS[:-1],
    )
    extra_component = _component("stream-event-decoder")
    extra = _selection(
        cast(
            tuple[RuntimeComponent, ...],
            (*fixture.selected_components, extra_component),
        ),
        (*_ROLE_IDS, "codec.stream.event-decoder"),
    )

    for selection in (missing, extra):
        # Build a replacement immutable fixture so factory validation cannot be
        # bypassed by mutating the original completed selection.
        changed = _FactoryFixture(
            fixture.integration_plan,
            selection,
            fixture.resource_limits,
            fixture.service_access_resolver,
            fixture.authorization_handler_resolver,
            fixture.authorization_handlers,
            fixture.capability_resolution,
            fixture.selected_components,
        )
        _assert_raises(
            ValueError,
            lambda changed=changed: _create(changed),
            "must contain exactly the unary execution roles",
        )


def test_factory_requires_behavior_for_every_selected_role() -> None:
    """Reject metadata-only selections at each executable role boundary."""
    fixture = _fixture()
    expected_fields = (
        "task_protocol_adapter",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
    )

    for index, field_name in enumerate(expected_fields):
        # Replace only one component with valid metadata but no behavior so each
        # fixed role proves its own protocol check rather than a shared first check.
        invalid = _DescriptorOnlyComponent(
            fixture.selected_components[index].descriptor
        )
        components = list(
            cast(tuple[RuntimeComponent, ...], fixture.selected_components)
        )
        components[index] = invalid
        selection = _selection(tuple(components))
        integration_plan = fixture.integration_plan
        if index == 0:
            # Keep plan/selection identity coherent so the test reaches the
            # adapter behavior gate rather than the earlier convergence check.
            integration_plan = _direct_plan(invalid)
        changed = _FactoryFixture(
            integration_plan,
            selection,
            fixture.resource_limits,
            fixture.service_access_resolver,
            fixture.authorization_handler_resolver,
            fixture.authorization_handlers,
            fixture.capability_resolution,
            fixture.selected_components,
        )

        _assert_raises(
            TypeError,
            lambda changed=changed: _create(changed),
            f"{field_name} must implement the declared behavior protocol",
        )


def test_factory_requires_type_contract_for_every_selected_role() -> None:
    """Reject executable role selections that lack type-validation evidence."""
    fixture = _fixture()
    expected_fields = (
        "task_protocol_adapter",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
    )

    for index, field_name in enumerate(expected_fields):
        # A complete behavior surface can pass selection, but a null contract
        # violates the minimum completed-input invariant for a data-bearing role.
        components = list(fixture.selected_components)
        components[index] = _component(
            f"missing-contract:{field_name}",
            has_type_contract=False,
        )
        selection = _selection(cast(tuple[RuntimeComponent, ...], tuple(components)))
        integration_plan = fixture.integration_plan
        if index == 0:
            # Preserve the exact adapter identity prerequisite while isolating
            # the missing type-contract failure owned by this test.
            integration_plan = _direct_plan(components[0])
        changed = _FactoryFixture(
            integration_plan,
            selection,
            fixture.resource_limits,
            fixture.service_access_resolver,
            fixture.authorization_handler_resolver,
            fixture.authorization_handlers,
            fixture.capability_resolution,
            tuple(components),
        )

        _assert_raises(
            ValueError,
            lambda changed=changed: _create(changed),
            f"selected {field_name} must declare a type contract",
        )


def test_factory_validates_completed_aggregate_boundaries_and_limits() -> None:
    """Reject structural aggregate substitutes and semantically invalid limits."""
    fixture = _fixture()

    # Each nominal result has its own precise boundary instead of failing later
    # through partial field access or silently treating a look-alike as completed.
    invalid_aggregates: tuple[tuple[_FactoryFixture, str], ...] = (
        (
            _FactoryFixture(
                cast(ModelIntegrationPlan, object()),
                fixture.component_selection,
                fixture.resource_limits,
                fixture.service_access_resolver,
                fixture.authorization_handler_resolver,
                fixture.authorization_handlers,
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "integration_plan must be a ModelIntegrationPlan",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                cast(ComponentSelectionResolution, object()),
                fixture.resource_limits,
                fixture.service_access_resolver,
                fixture.authorization_handler_resolver,
                fixture.authorization_handlers,
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "component_selection must be a ComponentSelectionResolution",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                cast(ResolvedInteractionResourceLimits, object()),
                fixture.service_access_resolver,
                fixture.authorization_handler_resolver,
                fixture.authorization_handlers,
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "resource_limits must be a ResolvedInteractionResourceLimits",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                fixture.resource_limits,
                fixture.service_access_resolver,
                fixture.authorization_handler_resolver,
                fixture.authorization_handlers,
                cast(CapabilityResolution, object()),
                fixture.selected_components,
            ),
            "capability_resolution must be a CapabilityResolution",
        ),
    )

    for changed, message in invalid_aggregates:
        _assert_raises(
            TypeError,
            lambda changed=changed: _create(changed),
            message,
        )

    # The nominal resolved-limits type still requires positive portable values at
    # the final retention boundary; constructor shape alone is insufficient.
    invalid_limits = ResolvedInteractionResourceLimits(0, 1_024, 512)
    changed = _FactoryFixture(
        fixture.integration_plan,
        fixture.component_selection,
        invalid_limits,
        fixture.service_access_resolver,
        fixture.authorization_handler_resolver,
        fixture.authorization_handlers,
        fixture.capability_resolution,
        fixture.selected_components,
    )
    _assert_raises(
        ValueError,
        lambda: _create(changed),
        "max_response_body_bytes must be positive",
    )


def test_factory_validates_input_dispatched_components_and_candidate_tuple() -> None:
    """Reject invalid resolvers, handlers, and mutable candidate membership."""
    fixture = _fixture()
    descriptor_only = _DescriptorOnlyComponent(
        ComponentDescriptor("metadata-only", "1", "application")
    )
    malformed_descriptor = _ExecutableComponent(cast(ComponentDescriptor, object()))

    # Resolvers are not ComponentRole entries, but they remain executable
    # behavior. Candidate membership must also be immutable and behavior-complete.
    invalid_inputs: tuple[tuple[_FactoryFixture, str], ...] = (
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                fixture.resource_limits,
                cast(_ExecutableComponent, descriptor_only),
                fixture.authorization_handler_resolver,
                fixture.authorization_handlers,
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "service_access_resolver must implement the declared behavior protocol",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                fixture.resource_limits,
                fixture.service_access_resolver,
                cast(_ExecutableComponent, descriptor_only),
                fixture.authorization_handlers,
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "authorization_handler_resolver must implement the declared behavior protocol",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                fixture.resource_limits,
                fixture.service_access_resolver,
                fixture.authorization_handler_resolver,
                cast(
                    tuple[_ExecutableComponent, ...],
                    list(fixture.authorization_handlers),
                ),
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "authorization_handlers must be a tuple",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                fixture.resource_limits,
                fixture.service_access_resolver,
                fixture.authorization_handler_resolver,
                cast(tuple[_ExecutableComponent, ...], (descriptor_only,)),
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "authorization_handlers must implement the declared behavior protocol",
        ),
        (
            _FactoryFixture(
                fixture.integration_plan,
                fixture.component_selection,
                fixture.resource_limits,
                malformed_descriptor,
                fixture.authorization_handler_resolver,
                fixture.authorization_handlers,
                fixture.capability_resolution,
                fixture.selected_components,
            ),
            "service_access_resolver descriptor must be a ComponentDescriptor",
        ),
    )

    for changed, message in invalid_inputs:
        _assert_raises(
            TypeError,
            lambda changed=changed: _create(changed),
            message,
        )


def test_factory_signature_exposes_only_completed_inputs() -> None:
    """Prevent raw role components, source layers, and validation flags as inputs."""
    signature = inspect.signature(create_interaction_execution_components)

    # Every input is explicit and keyword-only. Selected adapter/codec/transport
    # instances cannot disagree with the retained ComponentSelectionResolution.
    assert tuple(signature.parameters) == (
        "integration_plan",
        "component_selection",
        "resource_limits",
        "service_access_resolver",
        "authorization_handler_resolver",
        "authorization_handlers",
        "capability_resolution",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    for forbidden in (
        "task_protocol_adapter",
        "payload_encoder",
        "success_payload_decoder",
        "error_payload_decoder",
        "transport",
        "runtime_components",
        "source_layers",
        "type_contracts_validated",
        "capabilities_validated",
    ):
        assert forbidden not in signature.parameters
