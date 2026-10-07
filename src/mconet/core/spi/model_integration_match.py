"""Immutable composition of target and task execution match outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.spi.model_target_match import ModelTargetMatch
from mconet.core.spi.task_match import TaskMatch


@dataclass(frozen=True, slots=True)
class ModelIntegrationMatch:
    """Combine one target result with one task-and-mode result.

    The two nominal values retain independent decisions, scores, and diagnostics.
    This composition does not calculate an aggregate score, merge diagnostics,
    discard partial matches, or select a binding; those policies belong to the
    deterministic model integration resolver.
    """

    target: ModelTargetMatch
    """Match facts for service, protocol, model, and deployment target selection."""

    task: TaskMatch
    """Match facts for the task descriptor and requested interaction mode."""

    def __post_init__(self) -> None:
        """Require both completed nominal match result values."""
        target = cast(object, self.target)
        task = cast(object, self.task)

        # Preserve the target-specific nominal boundary so a task result or raw
        # mapping cannot enter the target position despite having similar fields.
        if not isinstance(target, ModelTargetMatch):
            raise TypeError("ModelIntegrationMatch target must be a ModelTargetMatch.")

        # TaskMatch already represents both TaskDescriptor and InteractionMode;
        # keep it intact rather than copying or aggregating its component facts.
        if not isinstance(task, TaskMatch):
            raise TypeError("ModelIntegrationMatch task must be a TaskMatch.")
