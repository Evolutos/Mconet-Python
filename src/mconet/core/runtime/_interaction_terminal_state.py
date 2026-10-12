"""Mutually exclusive terminal states for one interaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

InteractionTerminalKind = Literal["completed", "failed", "cancelled"]

_KINDS = frozenset(("completed", "failed", "cancelled"))


@dataclass(frozen=True, slots=True)
class InteractionTerminalState:
    """Record exactly one terminal outcome for an interaction.

    ``completed``, ``failed``, and ``cancelled`` are the only kinds. One value
    carries one kind, so the three outcomes cannot be true together. Changing
    an interaction from one terminal outcome to another belongs to the
    once-only state machine, not to this value.
    """

    kind: InteractionTerminalKind
    """The single terminal outcome represented by this value."""

    def __post_init__(self) -> None:
        """Reject a kind outside the three terminal outcomes."""
        kind = cast(object, self.kind)
        if not isinstance(kind, str) or kind not in _KINDS:
            raise ValueError(
                "InteractionTerminalState kind must be completed, failed, or cancelled."
            )

    @property
    def completed(self) -> bool:
        """Return whether this value is the completed outcome."""
        return self.kind == "completed"

    @property
    def failed(self) -> bool:
        """Return whether this value is the failed outcome."""
        return self.kind == "failed"

    @property
    def cancelled(self) -> bool:
        """Return whether this value is the cancelled outcome."""
        return self.kind == "cancelled"
