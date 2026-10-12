"""Runtime stop when protocol planning fails before a credential read."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)

_T = TypeVar("_T")
_U = TypeVar("_U")


def run_planning_gate(
    plan: Callable[[], _T],
    read_credential: Callable[[_T], _U],
    machine: InteractionTerminalMachine,
) -> _U:
    """Plan one interaction and read a credential only after planning returns.

    A ``ModelInteractionError`` from planning fails the interaction once and
    is re-raised. The credential reader is not called.

    Args:
        plan: Protocol-planning stage.
        read_credential: Credential stage. It runs only after planning returns.
        machine: Terminal machine for this interaction.

    Returns:
        The value returned by the credential reader.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If planning fails. The machine is then failed.
    """
    plan_value = cast(object, plan)
    credential_value = cast(object, read_credential)
    machine_value = cast(object, machine)
    if not isinstance(plan_value, Callable):
        raise TypeError("plan must be callable.")
    if not isinstance(credential_value, Callable):
        raise TypeError("read_credential must be callable.")
    if not isinstance(machine_value, InteractionTerminalMachine):
        raise TypeError("machine must be an InteractionTerminalMachine.")
    checked_plan = cast(Callable[[], _T], plan_value)
    checked_credential = cast(Callable[[_T], _U], credential_value)
    try:
        planned = checked_plan()
    except ModelInteractionError:
        machine_value.fail()
        raise
    return checked_credential(planned)
