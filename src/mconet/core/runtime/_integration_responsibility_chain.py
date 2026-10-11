"""Internal ordered responsibility chain of compatibility bindings."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import InteractionMode, ModelTarget, TaskDescriptor
from mconet.core.runtime._model_integration_binding import (
    ModelIntegrationBinding,
    match_binding,
)
from mconet.core.runtime._model_integration_resolution_errors import (
    ambiguous_model_integration_error,
)
from mconet.core.spi import ModelIntegrationMatch


class IntegrationResponsibilityChain:
    """Ask explicitly ordered bindings in turn until one applies.

    The order is the declaration order and is the only tie-breaker. Match
    scores are recorded in the plan but never reorder the chain, so the
    first applicable binding always wins, independent of other entries. The
    chain is assembled once in code and has no register, add, or remove
    operation.
    """

    __slots__ = ("_bindings",)

    def __init__(self, bindings: tuple[ModelIntegrationBinding, ...]) -> None:
        """Build the chain from bindings in evaluation order.

        Args:
            bindings: Bindings in the order they are asked.

        Raises:
            TypeError: If ``bindings`` is not a tuple of bindings.
            ModelInteractionError: ``ambiguous_model_integration`` when two
                entries share a binding id, because a diagnostic naming that
                id could not tell which position matched.
        """
        if not isinstance(cast(object, bindings), tuple):
            raise TypeError("IntegrationResponsibilityChain bindings must be a tuple.")
        seen_ids: set[str] = set()
        for binding in cast(tuple[object, ...], bindings):
            if not isinstance(binding, ModelIntegrationBinding):
                raise TypeError(
                    "IntegrationResponsibilityChain bindings must be "
                    "ModelIntegrationBinding values."
                )
            if binding.id in seen_ids:
                raise ambiguous_model_integration_error()
            seen_ids.add(binding.id)
        self._bindings = bindings

    @property
    def binding_ids(self) -> tuple[str, ...]:
        """Return the binding ids in evaluation order, for diagnostics."""
        return tuple(binding.id for binding in self._bindings)

    def first_match(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> tuple[ModelIntegrationBinding, ModelIntegrationMatch] | None:
        """Return the first binding whose matchers both accept the request.

        Later bindings are not consulted once one applies.

        Args:
            target: Model target being resolved.
            task: Task descriptor being resolved.
            mode: Interaction mode being resolved.

        Returns:
            The applicable binding and its match facts, or ``None`` when no
            binding applies.

        Raises:
            TypeError: If a matcher returns a value of the wrong type.
        """
        for binding in self._bindings:
            match = match_binding(binding, target, task, mode)
            if match is not None:
                return binding, match
        return None
