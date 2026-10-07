"""Immutable outcome values produced by model target matchers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Diagnostic


@dataclass(frozen=True, slots=True)
class ModelTargetMatch:
    """Describe whether and how strongly one integration matches a target.

    ``matched`` is the explicit applicability decision. ``score`` remains an
    open integer owned by the matcher and later deterministic resolver policy;
    this value does not normalize, rank, or compare candidates. Diagnostics
    preserve ordered non-secret observations explaining the result.
    """

    matched: bool
    """Whether the evaluated integration supports the model target."""

    score: int
    """Matcher-owned integer strength used by later deterministic resolution."""

    diagnostics: tuple[Diagnostic, ...] = ()
    """Ordered immutable observations produced while matching the target."""

    def __post_init__(self) -> None:
        """Require exact primitive values and immutable diagnostic membership."""
        matched = cast(object, self.matched)
        score = cast(object, self.score)
        diagnostics = cast(object, self.diagnostics)

        # Exact bool membership prevents Python integers 0 and 1 from silently
        # replacing the matcher's explicit applicability decision.
        if type(matched) is not bool:
            raise TypeError("ModelTargetMatch matched must be a boolean.")

        # Scores remain open signed integers because ranking scale and range are
        # resolver policy. Exact membership still rejects bool and lossy floats.
        if type(score) is not int:
            raise TypeError("ModelTargetMatch score must be an integer.")

        # Tuple storage fixes diagnostic order and membership when matching ends;
        # each member must retain the established structured Diagnostic contract.
        if not isinstance(diagnostics, tuple):
            raise TypeError("ModelTargetMatch diagnostics must be a tuple.")
        for diagnostic in cast(tuple[object, ...], diagnostics):
            if not isinstance(diagnostic, Diagnostic):
                raise TypeError(
                    "ModelTargetMatch diagnostics must contain Diagnostic values."
                )
