"""Immutable outcome values produced by task and interaction-mode matchers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Diagnostic


@dataclass(frozen=True, slots=True)
class TaskMatch:
    """Describe whether and how strongly an integration matches task execution.

    A matcher evaluates both the task descriptor and interaction mode before
    creating this value. ``matched`` records its explicit applicability decision,
    ``score`` preserves its open integer strength, and diagnostics explain the
    result without retaining the task, mode, matcher, or runtime component.
    """

    matched: bool
    """Whether the evaluated integration supports the task and mode pair."""

    score: int
    """Matcher-owned integer strength used by later deterministic resolution."""

    diagnostics: tuple[Diagnostic, ...] = ()
    """Ordered immutable observations produced while matching task execution."""

    def __post_init__(self) -> None:
        """Require exact primitive values and immutable diagnostic membership."""
        matched = cast(object, self.matched)
        score = cast(object, self.score)
        diagnostics = cast(object, self.diagnostics)

        # Exact type membership keeps the applicability decision distinct from
        # Python integer values even though bool is an int subclass.
        if type(matched) is not bool:
            raise TypeError("TaskMatch matched must be a boolean.")

        # Preserve the matcher-owned signed integer without imposing a scale or
        # range. Resolver policy, rather than this carrier, interprets the score.
        if type(score) is not int:
            raise TypeError("TaskMatch score must be an integer.")

        # Tuple storage fixes the order and membership of observations at match
        # completion, while nominal members retain the Diagnostic safety contract.
        if not isinstance(diagnostics, tuple):
            raise TypeError("TaskMatch diagnostics must be a tuple.")
        for diagnostic in cast(tuple[object, ...], diagnostics):
            if not isinstance(diagnostic, Diagnostic):
                raise TypeError("TaskMatch diagnostics must contain Diagnostic values.")
