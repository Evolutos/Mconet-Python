"""Default type-table and responsibility-chain model integration resolver."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    InteractionMode,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.runtime._integration_responsibility_chain import (
    IntegrationResponsibilityChain,
)
from mconet.core.runtime._integration_type_key import IntegrationTypeKey
from mconet.core.runtime._integration_type_table import IntegrationTypeTable
from mconet.core.runtime._model_integration_binding import (
    ModelIntegrationBinding,
    match_binding,
)
from mconet.core.runtime._model_integration_resolution_errors import (
    unsupported_model_integration_error,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
)

DEFAULT_MODEL_INTEGRATION_RESOLVER_DESCRIPTOR = ComponentDescriptor(
    "default-model-integration-resolver",
    "1.0.0",
    "builtin",
)
"""Shared diagnostic metadata; the resolver declares no data ports."""

# Only these standard modes may use the protocol-level compatibility chain.
# Strict and every unknown future mode fail closed and use exact keys only.
_CHAIN_MODES = frozenset({OpenIdentifier("compatible"), OpenIdentifier("permissive")})


class DefaultModelIntegrationResolver:
    """Resolve a request through an exact type table, then an ordered chain.

    The fixed order is:

    1. the type table entry whose key equals the request's protocol, task
       type, and mode, when that binding's matchers also accept the request;
    2. for ``compatible`` and ``permissive`` only, the first chain binding
       whose matchers accept the request;
    3. otherwise ``unsupported_model_integration``.

    ``strict`` and unknown policy modes never reach the chain, because its
    rules are lower-specificity compatibility rules. A policy never relaxes
    an ambiguity: duplicate keys and repeated chain ids already failed when
    the table and chain were built. Resolution only evaluates matchers; it has
    no network, credential, encoding, or registry side effect.
    """

    __slots__ = ("_chain", "_table")

    def __init__(
        self,
        type_table: IntegrationTypeTable,
        responsibility_chain: IntegrationResponsibilityChain,
    ) -> None:
        """Create the resolver from already validated immutable parts.

        Args:
            type_table: Exact-key bindings consulted first.
            responsibility_chain: Ordered compatibility bindings consulted
                second under a relaxed policy.

        Raises:
            TypeError: If either part has the wrong type.
        """
        if not isinstance(cast(object, type_table), IntegrationTypeTable):
            raise TypeError(
                "DefaultModelIntegrationResolver type_table must be an "
                "IntegrationTypeTable."
            )
        if not isinstance(
            cast(object, responsibility_chain), IntegrationResponsibilityChain
        ):
            raise TypeError(
                "DefaultModelIntegrationResolver responsibility_chain must be an "
                "IntegrationResponsibilityChain."
            )
        self._table = type_table
        self._chain = responsibility_chain

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared diagnostic metadata."""
        return DEFAULT_MODEL_INTEGRATION_RESOLVER_DESCRIPTOR

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Return the resolved-binding plan for one request.

        Args:
            target: Validated model target.
            task: Validated task descriptor.
            mode: Requested interaction mode.
            policy: Resolved compatibility policy; it only decides whether the
                chain may be consulted.

        Returns:
            A plan snapshotting the selected binding's provenance, match
            facts, access defaults, and component candidates.

        Raises:
            TypeError: If ``policy`` is not a CompatibilityPolicy or a matcher
                returns a value of the wrong type.
            ModelInteractionError: ``unsupported_model_integration`` when no
                entry applies.
        """
        if not isinstance(cast(object, policy), CompatibilityPolicy):
            raise TypeError("policy must be a CompatibilityPolicy.")

        binding = self._table.lookup(IntegrationTypeKey.for_request(target, task, mode))
        if binding is not None:
            # A key names only protocol, task, and mode, so the binding's own
            # matchers still decide finer facts such as the service.
            match = match_binding(binding, target, task, mode)
            if match is not None:
                return _resolved_plan(binding, match)

        if policy.mode in _CHAIN_MODES:
            found = self._chain.first_match(target, task, mode)
            if found is not None:
                return _resolved_plan(*found)

        raise unsupported_model_integration_error()


def _resolved_plan(
    binding: ModelIntegrationBinding, match: ModelIntegrationMatch
) -> ModelIntegrationPlan:
    """Return the plan snapshot of one selected binding.

    Binding extensions are binding-internal assembly data and are not copied,
    so the plan's extensions stay empty.

    Args:
        binding: Selected binding.
        match: Successful match facts that selected it.

    Returns:
        A ``resolved_binding`` plan holding the binding's instances in order.
    """
    return ModelIntegrationPlan(
        source="resolved_binding",
        binding_id=binding.id,
        binding_version=binding.version,
        match=match,
        task_protocol_adapter=binding.task_protocol_adapter,
        authorization_handlers=binding.authorization_handlers,
        default_service_access=binding.default_service_access,
        payload_encoders=binding.payload_encoders,
        payload_decoders=binding.payload_decoders,
        transports=binding.transports,
    )
