"""Structural and outcome tests for model integration plan resolution."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import get_type_hints

from mconet.core.domain import (
    CompatibilityPolicy,
    ErrorCategory,
    Extensions,
    InteractionMode,
    InteractionPhase,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ModelTargetMatch,
    TaskMatch,
)


def _empty_extensions() -> Extensions:
    """Create independent portable storage for structural fixture values."""
    # Fresh mappings prevent fixture construction from sharing mutable input
    # before domain values or resolver implementations observe it.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete ordinary model target used by resolver calls."""

    service_id: OpenIdentifier
    """Open service identity."""

    protocol_id: OpenIdentifier
    """Open protocol identity."""

    model: ModelDescriptor
    """Exact model descriptor selected for the interaction."""

    deployment_id: str | None = None
    """Optional provider deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable target extension facts."""


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete ordinary task descriptor used by resolver calls."""

    type: OpenIdentifier
    """Open task identity."""

    version: str | None = None
    """Optional task contract version."""

    input_schema_id: str | None = None
    """Optional input schema identity."""

    output_schema_id: str | None = None
    """Optional output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive task metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable unknown task fields."""


@dataclass(frozen=True, slots=True)
class _Mode:
    """Ordinary open interaction mode used by resolver calls."""

    id: OpenIdentifier
    """Open execution-mode identity."""


@dataclass(frozen=True, slots=True)
class _Component:
    """Minimal concrete runtime component retained by fixture plans."""

    descriptor: ComponentDescriptor
    """Immutable component metadata used by plan validation."""


class _Resolver:
    """Configurable structural resolver returning one exact plan."""

    descriptor = ComponentDescriptor("Fixture resolver", "1.0.0", "application")
    """Stable metadata proving the fixture is a runtime component."""

    def __init__(self, result: ModelIntegrationPlan) -> None:
        """Store the plan and initialize an ordered invocation record."""
        # A prebuilt plan isolates the abstract protocol from the later default
        # type-table and responsibility-chain selection algorithms.
        self.result = result
        self.calls: list[
            tuple[
                ModelTarget,
                TaskDescriptor,
                InteractionMode,
                CompatibilityPolicy,
            ]
        ] = []

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Record the exact matching tuple and return the configured plan."""
        # Reference retention exposes input copying, normalization, hidden
        # lookups, or precedence behavior introduced by the protocol layer.
        self.calls.append((target, task, mode, policy))
        return self.result


class _FailingResolver:
    """Complete resolver propagating one configured deterministic failure."""

    descriptor = ComponentDescriptor("Failing resolver", "1.0.0", "application")
    """Valid metadata keeps failures focused on integration resolution."""

    def __init__(self, failure: ModelInteractionError) -> None:
        """Store the exact normalized resolution error to raise."""
        # Exception identity makes fallback, wrapping, retries, and secondary
        # component lookup observable in each failure branch.
        self.failure = failure

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Reject the complete matching tuple without a partial plan."""
        # All inputs are accepted before failure but never mutated or used for
        # network, credential, authorization, or registry operations.
        del target, task, mode, policy
        raise self.failure


class _IncompleteResolver:
    """Component-shaped fixture intentionally missing plan resolution."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates absence of the required resolve method."""


def _target() -> _Target:
    """Build one complete structural model target."""
    # Distinct target dimensions allow future resolver implementations to match
    # service, protocol, model, and deployment without parsing a combined ID.
    return _Target(
        service_id=OpenIdentifier("service.example"),
        protocol_id=OpenIdentifier("protocol.example"),
        model=NamedModel(
            "model-example",
            family=OpenIdentifier("model.family.example"),
        ),
        deployment_id="deployment-a",
        extensions={"target.region": "east"},
    )


def _task() -> _Task:
    """Build one complete structural task descriptor."""
    # Schema IDs remain separate from task identity and mode so matching cannot
    # infer one contract dimension from another.
    return _Task(
        type=OpenIdentifier("conversation.generate"),
        version="1.0.0",
        input_schema_id="schema://conversation-input",
        output_schema_id="schema://conversation-output",
        metadata={"task.variant": "standard"},
    )


def _mode() -> _Mode:
    """Build the open unary interaction mode fixture."""
    # The ordinary structural value proves resolution does not require an enum,
    # registry lookup, or one SDK-owned concrete mode class.
    return _Mode(OpenIdentifier("unary"))


def _adapter(name: str) -> _Component:
    """Build one concrete adapter-shaped runtime component."""
    # Plan identity retains the exact component instance; descriptor text exists
    # only for diagnostics and never acts as a lookup key.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _direct_plan() -> ModelIntegrationPlan:
    """Build the minimal plan for an already validated direct adapter."""
    # Direct provenance intentionally carries no binding metadata, match facts,
    # defaults, or binding-owned component candidates.
    return ModelIntegrationPlan(
        "direct_adapter",
        None,
        None,
        None,
        _adapter("Direct adapter"),
    )


def _resolved_plan() -> ModelIntegrationPlan:
    """Build one complete resolved binding snapshot."""
    # Independent match scores remain visible in the returned immutable plan;
    # no aggregate score or external binding object is retained.
    return ModelIntegrationPlan(
        "resolved_binding",
        "binding.example.conversation",
        "1.0.0",
        ModelIntegrationMatch(
            ModelTargetMatch(True, 400),
            TaskMatch(True, 200),
        ),
        _adapter("Resolved adapter"),
        extensions={"binding.owner": "fixture"},
    )


def _resolution_error(code: str) -> ModelInteractionError:
    """Build one normalized pre-interaction integration resolution failure."""
    # Unsupported and ambiguous branches share the same safe phase while their
    # stable SDK-owned codes remain independently assertable.
    category = (
        "unsupported_feature"
        if code == "unsupported_model_integration"
        else "invalid_component_configuration"
    )
    return ModelInteractionError(
        ErrorCategory(OpenIdentifier(category)),
        InteractionPhase(OpenIdentifier("model_integration_resolution")),
        code,
        "Model integration resolution failed.",
    )


def _accept_resolver(
    resolver: ModelIntegrationResolver,
) -> ModelIntegrationResolver:
    """Return a resolver after crossing the statically checked protocol boundary."""
    # Pyright verifies ordinary structural behavior without SDK inheritance,
    # registration, a component ID, or one prescribed lookup algorithm.
    return resolver


def test_model_integration_resolver_accepts_structural_class() -> None:
    """Require only component metadata and synchronous resolution behavior."""
    resolver = _Resolver(_resolved_plan())

    accepted = _accept_resolver(resolver)

    # Static and runtime structural conformance agree for an ordinary class.
    assert accepted is resolver
    assert isinstance(resolver, ModelIntegrationResolver)
    assert resolver.descriptor.name == "Fixture resolver"


def test_model_integration_resolver_preserves_inputs_and_resolved_plan() -> None:
    """Pass exact matching facts and return the exact resolved binding snapshot."""
    target = _target()
    task = _task()
    mode = _mode()
    policy = CompatibilityPolicy(OpenIdentifier("compatible"))
    expected = _resolved_plan()
    resolver = _Resolver(expected)

    result = resolver.resolve(target, task, mode, policy)

    # Identity checks prove the protocol layer neither rebuilds matching inputs
    # nor copies the immutable plan or any selected concrete adapter.
    assert resolver.calls == [(target, task, mode, policy)]
    assert resolver.calls[0][0] is target
    assert resolver.calls[0][1] is task
    assert resolver.calls[0][2] is mode
    assert resolver.calls[0][3] is policy
    assert result is expected
    assert result.source == "resolved_binding"
    assert result.task_protocol_adapter is expected.task_protocol_adapter


def test_model_integration_resolver_preserves_direct_plan_result() -> None:
    """Return a valid direct plan without inventing binding provenance."""
    expected = _direct_plan()
    resolver = _Resolver(expected)

    result = resolver.resolve(
        _target(),
        _task(),
        _mode(),
        CompatibilityPolicy(OpenIdentifier("strict")),
    )

    # A custom resolver result crosses unchanged; the minimal direct plan keeps
    # only its concrete adapter and cannot leak registry or binding state.
    assert result is expected
    assert result.source == "direct_adapter"
    assert result.binding_id is None
    assert result.binding_version is None
    assert result.match is None
    assert result.task_protocol_adapter is expected.task_protocol_adapter


def test_model_integration_resolver_propagates_not_found_failure() -> None:
    """Reject no matching integration without fabricating a fallback plan."""
    failure = _resolution_error("unsupported_model_integration")
    resolver = _FailingResolver(failure)

    try:
        resolver.resolve(
            _target(),
            _task(),
            _mode(),
            CompatibilityPolicy(OpenIdentifier("compatible")),
        )
    except ModelInteractionError as error:
        # Exact identity proves this boundary does not wrap the failure or select
        # an unrelated default through an external registry.
        assert error is failure
        assert error.code == "unsupported_model_integration"
    else:
        raise AssertionError("Expected unsupported model integration failure.")


def test_model_integration_resolver_propagates_ambiguity_failure() -> None:
    """Reject ambiguous matching without candidate-order selection."""
    failure = _resolution_error("ambiguous_model_integration")
    resolver = _FailingResolver(failure)

    try:
        resolver.resolve(
            _target(),
            _task(),
            _mode(),
            CompatibilityPolicy(OpenIdentifier("strict")),
        )
    except ModelInteractionError as error:
        # Ambiguity remains a stable configuration failure instead of allowing
        # first-match, last-match, name, or component-ID tie-breaking.
        assert error is failure
        assert error.code == "ambiguous_model_integration"
    else:
        raise AssertionError("Expected ambiguous model integration failure.")


def test_model_integration_resolver_has_exact_method_surface() -> None:
    """Lock matching input order, plan result, and synchronous semantics."""
    method = ModelIntegrationResolver.resolve
    annotations = get_type_hints(method)

    # The protocol receives domain matching facts and policy only; bindings,
    # registries, component IDs, requests, credentials, and transports are absent.
    assert tuple(inspect.signature(method).parameters) == (
        "self",
        "target",
        "task",
        "mode",
        "policy",
    )
    assert annotations == {
        "target": ModelTarget,
        "task": TaskDescriptor,
        "mode": InteractionMode,
        "policy": CompatibilityPolicy,
        "return": ModelIntegrationPlan,
    }
    assert not inspect.iscoroutinefunction(method)


def test_model_integration_resolver_requires_complete_behavior_surface() -> None:
    """Reject component metadata without integration resolution behavior."""
    incomplete = _IncompleteResolver()

    # Descriptor conformance alone cannot produce an integration plan.
    assert not isinstance(incomplete, ModelIntegrationResolver)


def test_model_integration_resolver_excludes_registry_and_external_effects() -> None:
    """Keep mutable registration, execution stages, and I/O out of the SPI."""
    resolver = _Resolver(_resolved_plan())

    # A concrete resolver may own private immutable lookup data, but callers
    # receive no public mutation, ID lookup, planning, authorization, or I/O API.
    for forbidden_member in (
        "register",
        "add",
        "remove",
        "lookup_component_id",
        "prepare_plan",
        "encode",
        "authorize",
        "send",
        "fetch",
    ):
        assert not hasattr(resolver, forbidden_member)
