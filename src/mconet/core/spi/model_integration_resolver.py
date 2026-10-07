"""Contract for deterministic model integration plan resolution."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain import (
    CompatibilityPolicy,
    InteractionMode,
    ModelTarget,
    TaskDescriptor,
)
from mconet.core.spi.model_integration_plan import ModelIntegrationPlan
from mconet.core.spi.runtime_component import RuntimeComponent


@runtime_checkable
class ModelIntegrationResolver(RuntimeComponent, Protocol):
    """Resolve one target, task, mode, and policy to one integration plan.

    Implementations use an immutable internal type table, a deterministic
    responsibility chain, or an equivalent private strategy to select exactly
    one integration. They return concrete component instances in the immutable
    :class:`ModelIntegrationPlan`; callers never register bindings or resolve
    component IDs through this public contract.

    Resolution is synchronous and side-effect-free. It must not perform network
    I/O, encode a request, read credentials, authorize or send a request, mutate
    any input, or consult a business-writable registry. No matching integration
    and an ambiguous integration are deterministic pre-interaction failures.

    Runtime handles a directly injected task protocol adapter before invoking a
    default resolver. The protocol can still return either valid plan source so
    custom implementations and contract fixtures preserve the complete result
    boundary without exposing Runtime's precedence algorithm.
    """

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Return the exact deterministic integration plan for the input tuple."""
        # All four original values remain visible so matching and compatibility
        # policy can be evaluated without reconstruction or hidden global state.
        ...
