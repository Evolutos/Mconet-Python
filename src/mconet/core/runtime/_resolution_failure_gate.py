"""Runtime stop when service resolution fails before planning."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)

_T = TypeVar("_T")
_U = TypeVar("_U")


def run_resolution_gate(
    resolve: Callable[[], _T],
    plan: Callable[[_T], _U],
    machine: InteractionTerminalMachine,
) -> _U:
    """Resolve one interaction and plan only after resolution returns.

    A ``ModelInteractionError`` from resolution fails the interaction once and
    is re-raised. Planning is not called. A second terminal transition is left
    to the machine, which rejects it.

    Args:
        resolve: Service-resolution stage.
        plan: Planning stage. It runs only after resolution returns.
        machine: Terminal machine for this interaction.

    Returns:
        The value returned by planning.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If resolution fails. The machine is then failed.
    """
    resolve_value = cast(object, resolve)
    plan_value = cast(object, plan)
    machine_value = cast(object, machine)
    if not isinstance(resolve_value, Callable):
        raise TypeError("resolve must be callable.")
    if not isinstance(plan_value, Callable):
        raise TypeError("plan must be callable.")
    if not isinstance(machine_value, InteractionTerminalMachine):
        raise TypeError("machine must be an InteractionTerminalMachine.")
    checked_resolve = cast(Callable[[], _T], resolve_value)
    checked_plan = cast(Callable[[_T], _U], plan_value)
    try:
        resolved = checked_resolve()
    except ModelInteractionError:
        machine_value.fail()
        raise
    return checked_plan(resolved)
