"""Direct-adapter integration plans and their precedence over resolution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    InteractionMode,
    ModelTarget,
    TaskDescriptor,
)
from mconet.core.runtime._model_integration_resolution_errors import (
    unsupported_direct_adapter_error,
)
from mconet.core.spi import (
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    TaskProtocolAdapter,
)


def direct_model_integration_plan(
    adapter: TaskProtocolAdapter,
    target: ModelTarget,
    task: TaskDescriptor,
    mode: InteractionMode,
) -> ModelIntegrationPlan:
    """Return the minimal plan for an adapter the caller injected directly.

    The default resolver is bypassed, but the adapter's own ``supports`` is
    still asked, so an injected adapter can never be used for a request it
    rejects. The plan carries only the adapter: no binding provenance, match
    facts, access defaults, or binding-owned candidates.

    Args:
        adapter: Task protocol adapter injected by the caller.
        target: Validated model target.
        task: Validated task descriptor.
        mode: Requested interaction mode.

    Returns:
        A ``direct_adapter`` plan holding the adapter instance.

    Raises:
        TypeError: If ``adapter`` is not a TaskProtocolAdapter or
            ``supports`` does not return a bool.
        ModelInteractionError: ``unsupported_model_integration`` when the
            adapter does not support the request. There is no fallback to the
            default resolver.
    """
    if not isinstance(cast(object, adapter), TaskProtocolAdapter):
        raise TypeError("adapter must implement TaskProtocolAdapter.")
    supported = cast(object, adapter.supports(target, task, mode))
    # Only an exact bool is accepted, so a truthy placeholder from a dynamic
    # implementation cannot be taken for support.
    if not isinstance(supported, bool):
        raise TypeError("TaskProtocolAdapter supports must return a bool.")
    if not supported:
        raise unsupported_direct_adapter_error()
    return ModelIntegrationPlan(
        source="direct_adapter",
        binding_id=None,
        binding_version=None,
        match=None,
        task_protocol_adapter=adapter,
    )


def select_model_integration_plan(
    direct_adapter: TaskProtocolAdapter | None,
    resolver: ModelIntegrationResolver,
    target: ModelTarget,
    task: TaskDescriptor,
    mode: InteractionMode,
    policy: CompatibilityPolicy,
) -> ModelIntegrationPlan:
    """Return the integration plan following the fixed precedence.

    An injected adapter always wins and the resolver is not called at all,
    even when the resolver would not know the protocol. Only without an
    injected adapter does the resolver receive the request and the policy.

    Args:
        direct_adapter: Adapter injected by the interaction or client, or
            ``None``.
        resolver: Resolver used when no adapter is injected.
        target: Validated model target.
        task: Validated task descriptor.
        mode: Requested interaction mode.
        policy: Resolved compatibility policy for the resolver.

    Returns:
        The direct plan, or the resolver's plan.

    Raises:
        TypeError: If an argument has the wrong type.
        ModelInteractionError: If the injected adapter rejects the request, or
            the resolver fails.
    """
    if direct_adapter is not None:
        return direct_model_integration_plan(direct_adapter, target, task, mode)
    if not isinstance(cast(object, resolver), ModelIntegrationResolver):
        raise TypeError("resolver must implement ModelIntegrationResolver.")
    return resolver.resolve(target, task, mode, policy)
