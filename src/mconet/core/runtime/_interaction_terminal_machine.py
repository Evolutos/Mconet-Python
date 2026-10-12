"""Once-only terminal transition for one interaction."""

from __future__ import annotations

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.runtime._interaction_terminal_state import (
    InteractionTerminalKind,
    InteractionTerminalState,
)

_INTERNAL = ErrorCategory(OpenIdentifier("internal"))
_RUNTIME = InteractionPhase(OpenIdentifier("runtime"))
_ALREADY_TERMINAL_CODE = "interaction_already_terminal"
_ALREADY_TERMINAL_MESSAGE = "The interaction has already terminated."


class InteractionTerminalMachine:
    """Accept one terminal transition and reject every later one.

    The first ``complete``, ``fail``, or ``cancel`` stores that outcome. A
    later call, including a repeat of the same outcome, leaves the stored
    outcome unchanged and fails with ``interaction_already_terminal``.
    """

    __slots__ = ("_state",)

    def __init__(self) -> None:
        """Start with no terminal outcome."""
        self._state: InteractionTerminalState | None = None

    @property
    def state(self) -> InteractionTerminalState | None:
        """Return the stored outcome, or None before the first transition."""
        return self._state

    def complete(self) -> InteractionTerminalState:
        """Record a successful completion when the interaction is still open."""
        return self._finish("completed")

    def fail(self) -> InteractionTerminalState:
        """Record a failure when the interaction is still open."""
        return self._finish("failed")

    def cancel(self) -> InteractionTerminalState:
        """Record a cancellation when the interaction is still open."""
        return self._finish("cancelled")

    def _finish(self, kind: InteractionTerminalKind) -> InteractionTerminalState:
        """Store the first outcome and reject any second transition."""
        if self._state is not None:
            raise ModelInteractionError(
                category=_INTERNAL,
                phase=_RUNTIME,
                code=_ALREADY_TERMINAL_CODE,
                message=_ALREADY_TERMINAL_MESSAGE,
            )
        self._state = InteractionTerminalState(kind)
        return self._state
