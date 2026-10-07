"""Reusable runtime assertions for TaskProtocolAdapter implementations."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.domain import (
    InteractionMode,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    TaskDescriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskProtocolAdapter,
    TransportResponseMetadata,
)

_ADAPTER_METHODS = (
    "supports",
    "prepare_plan",
    "build_request",
    "parse_response",
    "parse_error",
)

_ValueT = TypeVar("_ValueT")


class AdapterContractSuite:
    """Apply the shared synchronous contract to one task protocol adapter.

    The suite is independent of pytest, unittest, fixture file formats, and any
    concrete protocol payload. Callers load or construct language-neutral cases,
    invoke the relevant assertion method, and inspect each validated result with
    a zero-return assertion callback. Adapter failures and callback failures pass
    through unchanged so the owning test framework retains normal diagnostics.

    Runtime checks supplement static protocol conformance: the descriptor and
    every returned SDK value must use its nominal public type, ``supports`` must
    return an exact boolean, and a request plan must retain the same execution
    plan instance that was already used for component and capability selection.
    The suite invokes each adapter method exactly once per assertion and performs
    no encoding, authorization, transport, credential access, monitoring, output
    assembly, fixture loading, or protocol-specific comparison.
    """

    __slots__ = ("_adapter",)

    def __init__(self, adapter: TaskProtocolAdapter) -> None:
        """Validate and retain one structurally conforming synchronous adapter.

        Args:
            adapter: Custom or SDK adapter subjected to reusable contract cases.

        Raises:
            TypeError: If the object, descriptor, or operation shape violates
                the public adapter boundary.
        """
        adapter_value = cast(object, adapter)
        if not isinstance(adapter_value, TaskProtocolAdapter):
            raise TypeError("adapter must implement TaskProtocolAdapter.")
        descriptor_value = cast(object, adapter.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("adapter descriptor must be a ComponentDescriptor.")

        # Calling an async adapter method would only create a coroutine where the
        # core SPI requires an immediate value. Reject this once at suite setup.
        for method_name in _ADAPTER_METHODS:
            method = getattr(adapter, method_name)
            if iscoroutinefunction(method) or iscoroutinefunction(
                type(method).__call__
            ):
                raise TypeError("adapter operations must be synchronous.")
        self._adapter = adapter

    def assert_supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        *,
        expected: bool,
    ) -> None:
        """Assert exact applicability for one target, task, and mode case.

        Args:
            target: Model target from the reusable contract case.
            task: Task descriptor from the reusable contract case.
            mode: Interaction mode whose applicability is being checked.
            expected: Exact boolean required from the adapter.

        Raises:
            TypeError: If ``expected`` is not an exact boolean.
            AssertionError: If the adapter returns a non-boolean or a different
                applicability result.
            BaseException: Any exact failure raised by the adapter.
        """
        expected_value = cast(object, expected)
        if type(expected_value) is not bool:
            raise TypeError("expected must be a bool.")

        # One direct invocation preserves the contract case's input identities
        # and allows unexpected adapter failures to reach the test unchanged.
        actual = self._adapter.supports(target, task, mode)
        actual_value = cast(object, actual)
        if type(actual_value) is not bool:
            raise AssertionError("adapter supports must return a bool.")
        if actual_value is not expected:
            raise AssertionError("adapter supports returned an unexpected result.")

    def assert_prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
        *,
        assertion: Callable[[ProtocolExecutionPlan], None],
    ) -> None:
        """Validate one planning result and pass it to a caller assertion.

        Args:
            request: Validated model request supplied by the contract case.
            access: Resolved non-secret access conditions for planning.
            mode: Interaction mode governing the execution requirements.
            assertion: Synchronous callback asserting protocol-specific facts.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the adapter returns no ProtocolExecutionPlan.
            BaseException: Any exact adapter or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        actual = self._adapter.prepare_plan(request, access, mode)
        # Only protocol-specific tests know which selections, ports, and
        # extensions their fixtures require; preserve the nominal result intact.
        actual_value = cast(object, actual)
        if not isinstance(actual_value, ProtocolExecutionPlan):
            raise AssertionError(
                "adapter prepare_plan must return a ProtocolExecutionPlan."
            )
        checked_assertion(actual_value)

    def assert_build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
        *,
        assertion: Callable[[ProtocolRequestPlan], None],
    ) -> None:
        """Validate one request plan and its prepared-plan identity.

        Args:
            request: Validated model request supplied by the contract case.
            plan: Prepared plan already used for downstream component selection.
            assertion: Synchronous callback asserting payload and request facts.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the result has an invalid type or replaces
                ``plan`` with another execution plan instance.
            BaseException: Any exact adapter or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        actual = self._adapter.build_request(request, plan)
        actual_value = cast(object, actual)
        if not isinstance(actual_value, ProtocolRequestPlan):
            raise AssertionError(
                "adapter build_request must return a ProtocolRequestPlan."
            )
        if actual_value.execution_plan is not plan:
            # Component/type/capability selection has already consumed this plan;
            # accepting a replacement here would bypass those completed checks.
            raise AssertionError(
                "adapter build_request must retain the prepared plan instance."
            )
        checked_assertion(actual_value)

    def assert_parse_response(
        self,
        response: ErasedRuntimeValue,
        *,
        assertion: Callable[[ParsedTaskResponse], None],
    ) -> None:
        """Validate successful response parsing and inspect service facts.

        Args:
            response: Decoded protocol-native successful payload.
            assertion: Synchronous callback asserting parsed service facts.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the adapter returns no ParsedTaskResponse.
            BaseException: Any exact adapter or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        actual = self._adapter.parse_response(response)
        actual_value = cast(object, actual)
        if not isinstance(actual_value, ParsedTaskResponse):
            raise AssertionError(
                "adapter parse_response must return a ParsedTaskResponse."
            )
        checked_assertion(actual_value)

    def assert_parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
        *,
        assertion: Callable[[ModelInteractionError | None], None],
    ) -> None:
        """Validate recognized or unrecognized service-error parsing.

        Args:
            error: Decoded protocol-native error payload.
            metadata: Normalized transport response facts for the error outcome.
            assertion: Synchronous callback inspecting the mapped error or None.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the adapter returns an invalid error value.
            BaseException: Any exact adapter or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        actual = self._adapter.parse_error(error, metadata)
        actual_value = cast(object, actual)
        if actual_value is not None and not isinstance(
            actual_value, ModelInteractionError
        ):
            raise AssertionError(
                "adapter parse_error must return a ModelInteractionError or None."
            )
        # None remains a meaningful unrecognized-payload outcome and is passed
        # to the contract case instead of being converted into a fallback error.
        checked_assertion(actual_value)


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous callable before invoking the adapter operation."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # An async callback would not execute its assertions when called by this
        # synchronous suite and would leave an unawaited coroutine behind.
        raise TypeError("assertion must be synchronous.")
    return assertion
