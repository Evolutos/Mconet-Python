"""Tests that an interaction terminates only once."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import ModelInteractionError
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._interaction_terminal_state import InteractionTerminalState


def test_first_transition_is_stored() -> None:
    """Verify each first outcome is recorded and returned."""
    completed = InteractionTerminalMachine()
    failed = InteractionTerminalMachine()
    cancelled = InteractionTerminalMachine()

    assert completed.complete() == InteractionTerminalState("completed")
    assert failed.fail() == InteractionTerminalState("failed")
    assert cancelled.cancel() == InteractionTerminalState("cancelled")
    assert completed.state == InteractionTerminalState("completed")
    assert failed.state == InteractionTerminalState("failed")
    assert cancelled.state == InteractionTerminalState("cancelled")


def test_repeated_transitions_are_rejected() -> None:
    """Verify a second complete, fail, or cancel does not replace the first."""
    completed = InteractionTerminalMachine()
    failed = InteractionTerminalMachine()
    cancelled = InteractionTerminalMachine()
    completed.complete()
    failed.fail()
    cancelled.cancel()
    _reject_later_transitions(completed, InteractionTerminalState("completed"))
    _reject_later_transitions(failed, InteractionTerminalState("failed"))
    _reject_later_transitions(cancelled, InteractionTerminalState("cancelled"))


def _reject_later_transitions(
    machine: InteractionTerminalMachine,
    expected: InteractionTerminalState,
) -> None:
    """Require every later transition to fail without replacing the outcome."""
    actions: tuple[Callable[[], InteractionTerminalState], ...] = (
        machine.complete,
        machine.fail,
        machine.cancel,
    )
    for action in actions:
        error = _capture(action)
        assert isinstance(error, ModelInteractionError)
        assert error.code == "interaction_already_terminal"
        assert machine.state == expected


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
