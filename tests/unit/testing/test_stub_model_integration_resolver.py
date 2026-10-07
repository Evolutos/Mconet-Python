"""Configured outcome tests for StubModelIntegrationResolver."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import cast, get_type_hints

from mconet.core.domain import (
    CompatibilityPolicy,
    ErrorCategory,
    InteractionMode,
    InteractionPhase,
    ModelInteractionError,
    ModelTarget,
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
from mconet.testing import StubModelIntegrationResolver


@dataclass(frozen=True, slots=True)
class _Component:
    """Minimal concrete runtime component retained by configured plans."""

    descriptor: ComponentDescriptor
    """Immutable metadata satisfying the runtime component boundary."""


def _component(name: str) -> _Component:
    """Build one component with diagnostic metadata only."""
    # Plan validation needs only RuntimeComponent conformance; behavior belongs
    # to the component-specific contract tests rather than this resolver Stub.
    return _Component(ComponentDescriptor(name, "1", "application"))


def _direct_plan() -> ModelIntegrationPlan:
    """Build the minimal valid direct-adapter outcome."""
    # A direct plan contains no binding provenance, match, defaults, or binding-
    # owned candidates because Runtime already chose the explicit adapter.
    return ModelIntegrationPlan(
        "direct_adapter",
        None,
        None,
        None,
        _component("Direct adapter"),
    )


def _resolved_plan() -> ModelIntegrationPlan:
    """Build one complete valid resolved-binding outcome."""
    # Independent successful match facts and provenance make this observably
    # distinct from the direct path without invoking a real matching algorithm.
    return ModelIntegrationPlan(
        "resolved_binding",
        "binding.example.conversation",
        "1.0.0",
        ModelIntegrationMatch(
            ModelTargetMatch(True, 400),
            TaskMatch(True, 200),
        ),
        _component("Resolved adapter"),
        extensions={"binding.owner": "fixture"},
    )


def _resolution_error(code: str) -> ModelInteractionError:
    """Build one configured normalized resolver failure."""
    # Not-found is an unsupported target/task combination, while ambiguity is
    # invalid component configuration; both fail before interaction execution.
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


def _inputs() -> tuple[
    ModelTarget,
    TaskDescriptor,
    InteractionMode,
    CompatibilityPolicy,
]:
    """Create opaque typed inputs for a predetermined Stub outcome."""
    # The Stub must not inspect matching facts. Distinct sentinel objects ensure
    # its behavior depends only on construction-time configuration.
    return (
        cast(ModelTarget, object()),
        cast(TaskDescriptor, object()),
        cast(InteractionMode, object()),
        CompatibilityPolicy(OpenIdentifier("compatible")),
    )


def _resolve(stub: StubModelIntegrationResolver) -> ModelIntegrationPlan:
    """Invoke one Stub with a complete resolver protocol argument tuple."""
    target, task, mode, policy = _inputs()
    # Keeping the call in one helper makes every outcome exercise the same exact
    # public signature without introducing a private matching fixture model.
    return stub.resolve(target, task, mode, policy)


def _assert_raises_identity(
    stub: StubModelIntegrationResolver,
    expected: BaseException,
) -> None:
    """Require one resolution call to raise the exact configured failure."""
    try:
        _resolve(stub)
    except BaseException as error:
        # Identity proves the Stub neither wraps normalized integration errors
        # nor replaces them with fallback or candidate-selection failures.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_model_integration_resolver() -> None:
    """Expose complete resolution behavior without inheritance or registration."""
    stub = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_plan(),
    )

    accepted: ModelIntegrationResolver = stub

    # Static and runtime recognition agree on the same ordinary object and its
    # descriptor, without a component ID, SDK base class, or registry binding.
    assert accepted is stub
    assert isinstance(stub, ModelIntegrationResolver)
    assert stub.descriptor.name == "Stub resolver"


def test_stub_returns_exact_direct_plan() -> None:
    """Preserve the configured direct-adapter plan without binding metadata."""
    expected = _direct_plan()
    stub = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )

    result = _resolve(stub)

    # Exact identity and source facts prove the Stub neither copies the plan nor
    # invents a binding, match result, fallback, or replacement adapter.
    assert result is expected
    assert result.source == "direct_adapter"
    assert result.binding_id is None
    assert result.match is None
    assert result.task_protocol_adapter is expected.task_protocol_adapter


def test_stub_returns_exact_resolved_binding_plan() -> None:
    """Preserve the configured resolved plan and complete match provenance."""
    expected = _resolved_plan()
    stub = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )

    result = _resolve(stub)

    # The complete prebuilt snapshot crosses unchanged; the Stub does not rerun
    # scoring, reorder candidates, or rebuild the selected adapter instance.
    assert result is expected
    assert result.source == "resolved_binding"
    assert result.binding_id == "binding.example.conversation"
    assert result.match is expected.match
    assert result.task_protocol_adapter is expected.task_protocol_adapter


def test_stub_raises_exact_not_found_failure() -> None:
    """Configure no-match resolution without fabricating a fallback plan."""
    failure = _resolution_error("unsupported_model_integration")
    stub = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_plan(),
        error=failure,
    )

    _assert_raises_identity(stub, failure)

    # Stable normalized fields remain available exactly as configured for a
    # reusable resolver contract test.
    assert failure.code == "unsupported_model_integration"
    assert failure.category == ErrorCategory(OpenIdentifier("unsupported_feature"))


def test_stub_raises_exact_ambiguous_failure() -> None:
    """Configure ambiguous resolution without candidate-order tie-breaking."""
    failure = _resolution_error("ambiguous_model_integration")
    stub = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_plan(),
        error=failure,
    )

    _assert_raises_identity(stub, failure)

    # Ambiguity retains its configuration category and stable code rather than
    # falling back to first-match, last-match, name, or component-ID selection.
    assert failure.code == "ambiguous_model_integration"
    assert failure.category == ErrorCategory(
        OpenIdentifier("invalid_component_configuration")
    )


def test_stub_validates_configuration_eagerly() -> None:
    """Reject malformed metadata, result, and failure configuration."""
    descriptor = ComponentDescriptor("Stub resolver", "1", "application")
    plan = _resolved_plan()
    invalid_calls = (
        (
            lambda: StubModelIntegrationResolver(
                cast(ComponentDescriptor, object()), plan
            ),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubModelIntegrationResolver(
                descriptor,
                cast(ModelIntegrationPlan, object()),
            ),
            "result must be a ModelIntegrationPlan",
        ),
        (
            lambda: StubModelIntegrationResolver(
                descriptor,
                plan,
                error=cast(BaseException, "failure"),
            ),
            "error must be a BaseException or None",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Field-specific diagnostics keep malformed test setup separate from
            # the resolution failure that a configured scenario should exercise.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub configuration to fail.")


def test_stub_matches_resolver_surface_without_registry_controls() -> None:
    """Expose the exact resolver method without adjacent mutable behavior."""
    stub = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_plan(),
    )
    method = StubModelIntegrationResolver.resolve
    annotations = get_type_hints(method)

    # The concrete synchronous signature matches the SPI and returns only the
    # immutable plan boundary rather than an internal binding or component ID.
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

    # No generic recorder, mutable registry, matching implementation, fallback,
    # execution stage, or I/O surface belongs to this deterministic test double.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "register",
        "add",
        "remove",
        "match",
        "prepare_plan",
        "encode",
        "authorize",
        "send",
    ):
        assert not hasattr(stub, forbidden_member)
