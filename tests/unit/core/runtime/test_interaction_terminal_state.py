"""Tests that terminal outcomes are mutually exclusive."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.runtime._interaction_terminal_state import (
    InteractionTerminalKind,
    InteractionTerminalState,
)


def test_each_terminal_kind_excludes_the_other_two() -> None:
    """Verify a value reports exactly one of the three outcomes."""
    completed = InteractionTerminalState("completed")
    failed = InteractionTerminalState("failed")
    cancelled = InteractionTerminalState("cancelled")

    assert (completed.completed, completed.failed, completed.cancelled) == (
        True,
        False,
        False,
    )
    assert (failed.completed, failed.failed, failed.cancelled) == (
        False,
        True,
        False,
    )
    assert (cancelled.completed, cancelled.failed, cancelled.cancelled) == (
        False,
        False,
        True,
    )
    assert completed != failed
    assert failed != cancelled
    assert completed != cancelled


def test_unknown_kind_is_rejected() -> None:
    """Verify a fourth outcome cannot be stored."""
    try:
        InteractionTerminalState(cast(InteractionTerminalKind, "pending"))
    except ValueError as error:
        message = str(error)
    else:
        raise AssertionError("Expected an unknown kind to fail.")

    assert "completed, failed" in message


def test_terminal_state_is_immutable() -> None:
    """Verify one outcome cannot be rewritten into another."""
    state = InteractionTerminalState("completed")
    error = _capture(lambda: setattr(state, "kind", "failed"))

    assert isinstance(error, FrozenInstanceError)
    assert state.kind == "completed"


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
