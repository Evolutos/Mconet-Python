"""Snapshot and provenance tests for immutable model integration plans."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError, dataclass, field, fields
from typing import Literal, cast

from mconet.core.domain import (
    Authorization,
    Extensions,
    Headers,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelTargetMatch,
    RuntimeComponent,
    TaskMatch,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match plan-owned diagnostics so unrelated fixture errors cannot satisfy
        # a negative provenance or component-boundary assertion.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _empty_extensions() -> Extensions:
    """Create independent portable extension storage for test access values."""
    # A fresh dictionary prevents fixtures from sharing mutable setup state even
    # though ServiceAccess exposes the collection through a read-only protocol.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture satisfying the open domain protocol."""

    kind: OpenIdentifier
    """Open handler-selection discriminator."""


@dataclass(frozen=True, slots=True)
class _ServiceAccess:
    """Complete unresolved service access fixture for a binding snapshot."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers
    query: QueryParameters
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Component:
    """Concrete runtime component carrying immutable metadata."""

    descriptor: ComponentDescriptor
    """Static metadata observed by plan validation and later resolution."""


@dataclass(frozen=True, slots=True)
class _MissingDescriptor:
    """Invalid component fixture without the runtime metadata property."""

    value: str
    """Unrelated payload proving arbitrary objects are not components."""


@dataclass(frozen=True, slots=True)
class _MalformedComponent:
    """Structural component fixture containing non-nominal metadata."""

    descriptor: object
    """Invalid value used to exercise descriptor validation."""


def _component(name: str) -> _Component:
    """Build one distinguishable component for a resolved-plan role."""
    # Descriptor labels aid assertions, while plan behavior depends on retaining
    # this exact instance rather than reconstructing it from the label.
    return _Component(ComponentDescriptor(name, "1.0.0", "plugin"))


def _match(
    *,
    target_matched: bool = True,
    task_matched: bool = True,
) -> ModelIntegrationMatch:
    """Build explicit target and task/mode match facts for resolver output."""
    # Independent scores make it observable that the plan stores the complete
    # composition rather than an aggregate boolean or recomputed score.
    return ModelIntegrationMatch(
        ModelTargetMatch(target_matched, 400),
        TaskMatch(task_matched, 200),
    )


def _resolved_plan(
    *,
    extensions: Mapping[str, object] | None = None,
) -> ModelIntegrationPlan:
    """Build a complete resolved plan with current executable component roles."""
    # Each role uses an explicit concrete instance and immutable tuple so tests
    # can observe identity, order, and the absence of registry indirection.
    extension_values: Mapping[str, object] = {} if extensions is None else extensions
    return ModelIntegrationPlan(
        source="resolved_binding",
        binding_id="openai-compatible.conversation",
        binding_version="1.0.0",
        match=_match(),
        task_protocol_adapter=_component("task-adapter"),
        authorization_handlers=(
            _component("bearer-handler"),
            _component("anonymous-handler"),
        ),
        default_service_access=_ServiceAccess(
            endpoint=UriValue("https://models.example.test", True),
            authorization=_Authorization(OpenIdentifier("authorization.bearer")),
            headers=Headers(),
            query=QueryParameters(),
        ),
        payload_encoders=(_component("json-encoder"),),
        payload_decoders=(
            _component("json-success-decoder"),
            _component("json-error-decoder"),
        ),
        transports=(_component("http-transport"),),
        extensions=extension_values,
    )


def test_resolved_model_integration_plan_preserves_binding_snapshot() -> None:
    """Verify resolver provenance, match facts, and exact candidates remain fixed."""
    plan = _resolved_plan()

    # The public plan contains copied binding facts and concrete instances, not
    # the internal binding object, matcher objects, IDs requiring registry lookup,
    # or an aggregate match decision that discards detailed results.
    assert plan.source == "resolved_binding"
    assert plan.binding_id == "openai-compatible.conversation"
    assert plan.binding_version == "1.0.0"
    assert plan.match == _match()
    assert plan.match is not None
    assert plan.match.target.score == 400
    assert plan.match.task.score == 200
    assert plan.task_protocol_adapter.descriptor.name == "task-adapter"
    assert tuple(item.descriptor.name for item in plan.authorization_handlers) == (
        "bearer-handler",
        "anonymous-handler",
    )
    assert tuple(item.descriptor.name for item in plan.payload_decoders) == (
        "json-success-decoder",
        "json-error-decoder",
    )
    assert not hasattr(plan, "binding")
    assert not hasattr(plan, "target_matcher")
    assert not hasattr(plan, "task_matcher")
    assert not hasattr(plan, "component_ids")


def test_resolved_model_integration_plan_retains_component_identity_and_order() -> None:
    """Verify snapshot construction neither rebuilds nor reorders components."""
    adapter = _component("adapter")
    first_decoder = _component("first-decoder")
    second_decoder = _component("second-decoder")
    plan = ModelIntegrationPlan(
        "resolved_binding",
        "binding",
        "1",
        _match(),
        adapter,
        payload_decoders=(first_decoder, second_decoder),
    )

    # Concrete identity is the later resolver input, and tuple position preserves
    # deterministic candidate precedence independently from descriptor names.
    assert plan.task_protocol_adapter is adapter
    assert plan.payload_decoders[0] is first_decoder
    assert plan.payload_decoders[1] is second_decoder


def test_direct_model_integration_plan_contains_only_injected_adapter() -> None:
    """Verify the direct path has no binding provenance or candidate defaults."""
    adapter = _component("application-adapter")

    plan = ModelIntegrationPlan("direct_adapter", None, None, None, adapter)

    # Runtime validates adapter support before constructing this value. The plan
    # then bypasses the default integration resolver and uses later Client or SDK
    # component sources instead of pretending that a binding was selected.
    assert plan.source == "direct_adapter"
    assert plan.task_protocol_adapter is adapter
    assert plan.binding_id is None
    assert plan.binding_version is None
    assert plan.match is None
    assert plan.authorization_handlers == ()
    assert plan.default_service_access is None
    assert plan.payload_encoders == ()
    assert plan.payload_decoders == ()
    assert plan.transports == ()


def test_direct_model_integration_plan_rejects_binding_values() -> None:
    """Verify direct provenance cannot be combined with resolver-owned state."""
    adapter = _component("application-adapter")

    # Binding identity, matches, access defaults, and each candidate role would
    # create ambiguous precedence on a path that explicitly bypasses resolution.
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan("direct_adapter", "binding", None, None, adapter),
        "binding_id must be None",
    )
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan("direct_adapter", None, "1", None, adapter),
        "binding_version must be None",
    )
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan("direct_adapter", None, None, _match(), adapter),
        "match must be None",
    )
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan(
            "direct_adapter",
            None,
            None,
            None,
            adapter,
            payload_encoders=(_component("encoder"),),
        ),
        "payload_encoders must be empty",
    )
    access = _resolved_plan().default_service_access
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan(
            "direct_adapter",
            None,
            None,
            None,
            adapter,
            default_service_access=access,
        ),
        "default_service_access must be None",
    )


def test_resolved_model_integration_plan_requires_complete_successful_match() -> None:
    """Verify resolved provenance cannot carry missing or rejected match facts."""
    adapter = _component("adapter")

    # A resolved value is downstream proof of a selected binding. Candidate match
    # failures remain resolver diagnostics and cannot masquerade as a final plan.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan("resolved_binding", "binding", "1", None, adapter),
        "match must be a ModelIntegrationMatch",
    )
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            "binding",
            "1",
            _match(target_matched=False),
            adapter,
        ),
        "successful target and task results",
    )
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            "binding",
            "1",
            _match(task_matched=False),
            adapter,
        ),
        "successful target and task results",
    )


def test_model_integration_plan_requires_valid_source_and_binding_metadata() -> None:
    """Verify source and resolved binding identity use exact documented shapes."""
    adapter = _component("adapter")

    # The source is closed because it controls Runtime branching; binding labels
    # remain exact strings used only for diagnostics and monitoring snapshots.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            cast(Literal["direct_adapter", "resolved_binding"], 1),
            None,
            None,
            None,
            adapter,
        ),
        "source must be a string",
    )
    _assert_raises(
        ValueError,
        lambda: ModelIntegrationPlan(
            cast(Literal["direct_adapter", "resolved_binding"], "registry"),
            None,
            None,
            None,
            adapter,
        ),
        "source must be direct_adapter or resolved_binding",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding", cast(str, 1), "1", _match(), adapter
        ),
        "binding_id must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding", "binding", cast(str, 1), _match(), adapter
        ),
        "binding_version must be a string",
    )


def test_model_integration_plan_validates_components_and_access_shape() -> None:
    """Verify every snapshot role has concrete metadata and immutable membership."""
    plan = _resolved_plan()

    # Validate both the shared runtime protocol and nominal descriptor, then
    # reject mutable candidate collections and incomplete access defaults.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            plan.binding_id,
            plan.binding_version,
            plan.match,
            cast(RuntimeComponent, _MissingDescriptor("adapter")),
        ),
        "task_protocol_adapter must implement RuntimeComponent",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            plan.binding_id,
            plan.binding_version,
            plan.match,
            cast(RuntimeComponent, _MalformedComponent("descriptor")),
        ),
        "task_protocol_adapter descriptor must be a ComponentDescriptor",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            plan.binding_id,
            plan.binding_version,
            plan.match,
            plan.task_protocol_adapter,
            cast(tuple[RuntimeComponent, ...], []),
        ),
        "authorization_handlers must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            plan.binding_id,
            plan.binding_version,
            plan.match,
            plan.task_protocol_adapter,
            payload_decoders=(
                cast(RuntimeComponent, _MalformedComponent("descriptor")),
            ),
        ),
        "payload_decoders descriptor must be a ComponentDescriptor",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "resolved_binding",
            plan.binding_id,
            plan.binding_version,
            plan.match,
            plan.task_protocol_adapter,
            default_service_access=cast(ServiceAccess, object()),
        ),
        "default_service_access must implement ServiceAccess or be None",
    )


def test_model_integration_plan_snapshots_named_extensions() -> None:
    """Verify plan extension membership is detached and read-only."""
    marker: list[str] = ["opaque"]
    source: dict[str, object] = {"dialect": "vendor", "marker": marker}

    plan = _resolved_plan(extensions=source)
    source["dialect"] = "changed"
    source["later"] = True

    # Top-level membership is copied, while nested local values deliberately
    # retain identity because the SPI neither interprets nor deep-copies them.
    assert plan.extensions == {"dialect": "vendor", "marker": marker}
    assert plan.extensions["marker"] is marker
    assert "later" not in plan.extensions
    assert not hasattr(plan.extensions, "__setitem__")
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "direct_adapter",
            None,
            None,
            None,
            _component("adapter"),
            extensions=cast(Mapping[str, object], ()),
        ),
        "extensions must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationPlan(
            "direct_adapter",
            None,
            None,
            None,
            _component("adapter"),
            extensions=cast(Mapping[str, object], {1: "invalid"}),
        ),
        "extensions keys must be strings",
    )


def test_model_integration_plan_has_frozen_current_field_surface() -> None:
    """Verify the public value exposes only implemented integration roles."""
    plan = _resolved_plan()

    # Explicit fields prevent an untyped component map from becoming a hidden
    # registry. Future roles remain absent until their executable contracts exist.
    assert tuple(field.name for field in fields(ModelIntegrationPlan)) == (
        "source",
        "binding_id",
        "binding_version",
        "match",
        "task_protocol_adapter",
        "authorization_handlers",
        "default_service_access",
        "payload_encoders",
        "payload_decoders",
        "transports",
        "extensions",
    )
    assert not hasattr(plan, "components")
    assert not hasattr(plan, "artifact_readers")
    assert not hasattr(plan, "stream_framer_factories")
    assert not hasattr(plan, "operation_protocol_adapters")
    assert not hasattr(plan, "register")
    _assert_raises(
        FrozenInstanceError,
        lambda: plan.__setattr__("binding_version", "2"),
        "cannot assign to field",
    )
