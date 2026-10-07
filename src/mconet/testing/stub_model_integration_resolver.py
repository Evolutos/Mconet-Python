"""Configurable test double for model integration plan resolution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    InteractionMode,
    ModelTarget,
    TaskDescriptor,
)
from mconet.core.spi import ComponentDescriptor, ModelIntegrationPlan


class StubModelIntegrationResolver:
    """Return or raise one configured model integration resolution outcome.

    The stub structurally implements ``ModelIntegrationResolver`` without SDK
    inheritance. A direct-adapter or resolved-binding outcome is represented by
    the exact configured ``ModelIntegrationPlan``. Not-found and ambiguous
    outcomes are represented by exact configured failures, allowing tests to
    retain their stable normalized error fields and object identity.

    Resolution inputs cross the complete protocol boundary but are deliberately
    not inspected, copied, normalized, or retained. This test double performs no
    target or task matching, lookup, candidate scoring, fallback, network I/O,
    credential access, component construction, or mutable registration.

    Configuration is fixed at construction. The stub records no calls and has no
    reset or dynamic reconfiguration API; cross-component ordering belongs to the
    separate component call recorder.
    """

    __slots__ = ("_descriptor", "_error", "_result")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: ModelIntegrationPlan,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Validate and retain one deterministic integration resolution outcome.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            result: Exact direct or resolved plan returned on success.
            error: Optional exact not-found, ambiguous, or other failure raised
                instead of ``result``.

        Raises:
            TypeError: If metadata, the result, or the configured failure has an
                invalid nominal type.
        """
        descriptor_value = cast(object, descriptor)
        result_value = cast(object, result)
        error_value = cast(object, error)

        # Validate the complete fixed outcome at construction so malformed test
        # setup cannot escape into later component selection or request planning.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(result_value, ModelIntegrationPlan):
            raise TypeError("result must be a ModelIntegrationPlan.")
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")

        self._descriptor = descriptor
        self._result = result
        self._error = error

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after resolver selection or compatibility validation.
        return self._descriptor

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Return the configured plan or raise the configured resolution failure.

        Args:
            target: Model target accepted at the resolver protocol boundary.
            task: Task descriptor accepted at the resolver protocol boundary.
            mode: Requested interaction mode accepted without interpretation.
            policy: Compatibility policy accepted without interpretation.

        Returns:
            The exact configured direct or resolved integration plan.

        Raises:
            BaseException: The exact configured failure when one is present.
        """
        # A predetermined Stub outcome must not perform hidden matching, mutate
        # inputs, retain business values, or consult external state.
        del target, task, mode, policy
        if self._error is not None:
            # Preserve normalized error fields, identity, and control-flow class
            # instead of wrapping or translating not-found and ambiguous failures.
            raise self._error
        return self._result
