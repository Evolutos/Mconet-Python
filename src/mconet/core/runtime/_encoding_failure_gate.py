"""Runtime stop when payload encoding fails before authorization."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)

_T = TypeVar("_T")
_U = TypeVar("_U")


def run_encoding_gate(
    encode: Callable[[], _T],
    authorize: Callable[[_T], _U],
    machine: InteractionTerminalMachine,
) -> _U:
    """Encode one payload and authorize only after encoding returns.

    A ``ModelInteractionError`` from encoding fails the interaction once and
    is re-raised. The authorization handler is not called.

    Args:
        encode: Payload-encoding stage.
        authorize: Authorization stage. It runs only after encoding returns.
        machine: Terminal machine for this interaction.

    Returns:
        The value returned by authorization.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If encoding fails. The machine is then failed.
    """
    encode_value = cast(object, encode)
    authorize_value = cast(object, authorize)
    machine_value = cast(object, machine)
    if not isinstance(encode_value, Callable):
        raise TypeError("encode must be callable.")
    if not isinstance(authorize_value, Callable):
        raise TypeError("authorize must be callable.")
    if not isinstance(machine_value, InteractionTerminalMachine):
        raise TypeError("machine must be an InteractionTerminalMachine.")
    checked_encode = cast(Callable[[], _T], encode_value)
    checked_authorize = cast(Callable[[_T], _U], authorize_value)
    try:
        encoded = checked_encode()
    except ModelInteractionError:
        machine_value.fail()
        raise
    return checked_authorize(encoded)
