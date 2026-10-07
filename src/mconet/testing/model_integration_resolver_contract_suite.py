"""Reusable branch assertions for ModelIntegrationResolver implementations."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import Literal, TypeVar, cast

from mconet.core.domain import (
    CompatibilityPolicy,
    InteractionMode,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
    validate_model_target,
    validate_open_identifier,
    validate_task_descriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
)

_ValueT = TypeVar("_ValueT")
_PlanSource = Literal["direct_adapter", "resolved_binding"]


class ModelIntegrationResolverContractSuite:
    """Apply direct, resolved, missing, and ambiguous resolver contracts.

    The suite is independent of pytest, unittest, concrete model protocols,
    fixture formats, and resolver lookup strategies. Callers provide one valid
    target, task, interaction mode, and compatibility policy, then inspect the
    exact plan or exact failure through a synchronous assertion callback.

    Runtime checks supplement static protocol conformance. Successful cases must
    return a nominal :class:`ModelIntegrationPlan` with the branch-specific
    source, while failure cases must not return a fallback plan. Every assertion
    invokes ``resolve`` exactly once and performs no matching, candidate scoring,
    registry lookup, component selection, request planning, authorization,
    credential access, network I/O, fallback, retry, or input mutation.
    """

    __slots__ = ("_resolver",)

    def __init__(self, resolver: ModelIntegrationResolver) -> None:
        """Validate and retain one structurally conforming sync resolver.

        Args:
            resolver: Custom or SDK resolver subjected to reusable cases.

        Raises:
            TypeError: If the object, descriptor, or resolve operation violates
                the public resolver boundary.
        """
        resolver_value = cast(object, resolver)
        if not isinstance(resolver_value, ModelIntegrationResolver):
            raise TypeError("resolver must implement ModelIntegrationResolver.")
        descriptor_value = cast(object, resolver.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("resolver descriptor must be a ComponentDescriptor.")

        # Integration resolution must finish before component selection starts.
        # Reject async look-alikes that would return an unawaited coroutine.
        resolve = resolver.resolve
        if iscoroutinefunction(resolve) or iscoroutinefunction(type(resolve).__call__):
            raise TypeError("resolver operation must be synchronous.")
        self._resolver = resolver

    def assert_direct(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
        *,
        assertion: Callable[[ModelIntegrationPlan], None],
    ) -> None:
        """Validate one successful direct-adapter plan.

        Args:
            target: Exact validated model target for the contract case.
            task: Exact validated task descriptor for matching.
            mode: Exact open interaction mode requested by the caller.
            policy: Exact compatibility policy visible during resolution.
            assertion: Synchronous callback asserting direct-plan facts.

        Raises:
            TypeError: If an input or ``assertion`` violates its public shape.
            AssertionError: If the resolver returns no direct-adapter plan.
            BaseException: Any exact resolver or assertion callback failure.
        """
        # Validate all caller-owned setup before the only resolver invocation so
        # malformed contract cases cannot be mistaken for resolver behavior.
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(target, task, mode, policy)
        _assert_plan(
            self._resolver,
            target,
            task,
            mode,
            policy,
            expected_source="direct_adapter",
            assertion=checked_assertion,
        )

    def assert_resolved(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
        *,
        assertion: Callable[[ModelIntegrationPlan], None],
    ) -> None:
        """Validate one successful resolved-binding plan.

        Args:
            target: Exact validated model target for the contract case.
            task: Exact validated task descriptor for matching.
            mode: Exact open interaction mode requested by the caller.
            policy: Exact compatibility policy visible during resolution.
            assertion: Synchronous callback asserting resolved-plan facts.

        Raises:
            TypeError: If an input or ``assertion`` violates its public shape.
            AssertionError: If the resolver returns no resolved-binding plan.
            BaseException: Any exact resolver or assertion callback failure.
        """
        # The same input validation applies to both successful provenance paths;
        # only the required plan source differs after resolution completes.
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(target, task, mode, policy)
        _assert_plan(
            self._resolver,
            target,
            task,
            mode,
            policy,
            expected_source="resolved_binding",
            assertion=checked_assertion,
        )

    def assert_not_found(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require resolution to reject inputs with no matching integration.

        Args:
            target: Exact validated model target for the negative case.
            task: Exact validated task descriptor for matching.
            mode: Exact open interaction mode requested by the caller.
            policy: Exact compatibility policy visible during resolution.
            assertion: Synchronous callback asserting no-match failure facts.

        Raises:
            TypeError: If an input or ``assertion`` violates its public shape.
            AssertionError: If the resolver returns a fallback plan.
            BaseException: Any exact assertion callback failure.
        """
        # Validate before resolution so the callback receives only an actual
        # no-match failure, never a suite-owned input-validation exception.
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(target, task, mode, policy)
        _assert_resolution_failure(
            self._resolver,
            target,
            task,
            mode,
            policy,
            assertion=checked_assertion,
            success_message=(
                "resolver was expected to find no matching model integration."
            ),
        )

    def assert_ambiguous(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require resolution to reject an ambiguous integration match.

        Args:
            target: Exact validated model target for the negative case.
            task: Exact validated task descriptor for matching.
            mode: Exact open interaction mode requested by the caller.
            policy: Exact compatibility policy visible during resolution.
            assertion: Synchronous callback asserting ambiguity failure facts.

        Raises:
            TypeError: If an input or ``assertion`` violates its public shape.
            AssertionError: If the resolver chooses an ambiguous candidate.
            BaseException: Any exact assertion callback failure.
        """
        # Ambiguity uses its own entry point and success diagnostic even though
        # exact failure capture is shared with the no-match branch.
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(target, task, mode, policy)
        _assert_resolution_failure(
            self._resolver,
            target,
            task,
            mode,
            policy,
            assertion=checked_assertion,
            success_message=(
                "resolver was expected to reject ambiguous model integrations."
            ),
        )


def _validate_inputs(
    target: ModelTarget,
    task: TaskDescriptor,
    mode: InteractionMode,
    policy: CompatibilityPolicy,
) -> None:
    """Require complete valid domain inputs before invoking the resolver."""
    # Reuse the public validators so the suite cannot evolve a competing target
    # or task interpretation. Both functions preserve the exact input objects.
    validate_model_target(target)
    validate_task_descriptor(task)

    mode_value = cast(object, mode)
    if not isinstance(mode_value, InteractionMode):
        raise TypeError("mode must implement InteractionMode.")
    mode_id = cast(object, mode.id)
    if not isinstance(mode_id, OpenIdentifier):
        raise TypeError("InteractionMode id must be an OpenIdentifier.")
    validate_open_identifier(mode_id)

    policy_value = cast(object, policy)
    if not isinstance(policy_value, CompatibilityPolicy):
        raise TypeError("policy must be a CompatibilityPolicy.")


def _assert_plan(
    resolver: ModelIntegrationResolver,
    target: ModelTarget,
    task: TaskDescriptor,
    mode: InteractionMode,
    policy: CompatibilityPolicy,
    *,
    expected_source: _PlanSource,
    assertion: Callable[[ModelIntegrationPlan], None],
) -> None:
    """Resolve once and require the nominal plan and expected provenance."""
    # One direct call preserves every input identity and lets an unexpected
    # resolver failure reach the owning test framework without translation.
    actual = resolver.resolve(target, task, mode, policy)
    actual_value = cast(object, actual)
    if not isinstance(actual_value, ModelIntegrationPlan):
        raise AssertionError("resolver must return a ModelIntegrationPlan.")
    if actual_value.source != expected_source:
        # Keep source mismatch diagnostics implementation-owned; plan extension
        # values or binding identifiers are not safe or necessary to render.
        raise AssertionError(
            f"resolver must return a {expected_source} integration plan."
        )
    assertion(actual_value)


def _assert_resolution_failure(
    resolver: ModelIntegrationResolver,
    target: ModelTarget,
    task: TaskDescriptor,
    mode: InteractionMode,
    policy: CompatibilityPolicy,
    *,
    assertion: Callable[[BaseException], None],
    success_message: str,
) -> None:
    """Invoke one failure branch and expose the exact resolver failure."""
    try:
        # Catch BaseException deliberately so cancellation or interruption used
        # by a custom contract fixture retains its exact type and identity.
        resolver.resolve(target, task, mode, policy)
    except BaseException as error:
        captured_error = error
    else:
        raise AssertionError(success_message)

    # Execute outside the catch block so a callback failure cannot be mistaken
    # for, wrapped with, or otherwise conflated with the resolution failure.
    assertion(captured_error)


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous assertion before invoking the resolver."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # Async callbacks would leave contract assertions unexecuted and create
        # an unawaited coroutine in this deliberately synchronous suite.
        raise TypeError("assertion must be synchronous.")
    return assertion
