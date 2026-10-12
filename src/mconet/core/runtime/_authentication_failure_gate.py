"""Runtime stop when authorization fails before transport."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)

_AUTHENTICATION = ErrorCategory(OpenIdentifier("authentication"))
_PHASE = InteractionPhase(OpenIdentifier("authentication"))
_FAILED_CODE = "authentication_failed"
_FAILED_MESSAGE = "Authorization failed."

_T = TypeVar("_T")
_U = TypeVar("_U")


def run_authentication_gate(
    authenticate: Callable[[], _T],
    send: Callable[[_T], _U],
    machine: InteractionTerminalMachine,
) -> _U:
    """Authorize one request and send only after authorization returns.

    A ``ModelInteractionError`` is re-raised by identity. Any other exception
    becomes ``authentication_failed`` whose message does not include the
    original text. Transport is not called. The interaction fails once.

    Args:
        authenticate: Authorization stage.
        send: Transport stage. It runs only after authorization returns.
        machine: Terminal machine for this interaction.

    Returns:
        The value returned by transport.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If authorization fails. The machine is then
            failed.
    """
    authenticate_value = cast(object, authenticate)
    send_value = cast(object, send)
    machine_value = cast(object, machine)
    if not isinstance(authenticate_value, Callable):
        raise TypeError("authenticate must be callable.")
    if not isinstance(send_value, Callable):
        raise TypeError("send must be callable.")
    if not isinstance(machine_value, InteractionTerminalMachine):
        raise TypeError("machine must be an InteractionTerminalMachine.")
    checked_authenticate = cast(Callable[[], _T], authenticate_value)
    checked_send = cast(Callable[[_T], _U], send_value)
    try:
        authorized = checked_authenticate()
    except ModelInteractionError:
        machine_value.fail()
        raise
    except Exception as error:
        machine_value.fail()
        raise ModelInteractionError(
            category=_AUTHENTICATION,
            phase=_PHASE,
            code=_FAILED_CODE,
            message=_FAILED_MESSAGE,
            cause=error,
        ) from error
    return checked_send(authorized)
