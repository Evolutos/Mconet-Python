"""Classification of transport failures into network, timeout, and cancel."""

from __future__ import annotations

import asyncio
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)

_NETWORK = ErrorCategory(OpenIdentifier("network"))
_TIMEOUT = ErrorCategory(OpenIdentifier("timeout"))
_CANCELLATION = ErrorCategory(OpenIdentifier("cancellation"))
_TRANSPORT = InteractionPhase(OpenIdentifier("transport"))
_NETWORK_CODE = "network_error"
_NETWORK_MESSAGE = "The network operation failed."
_TIMEOUT_CODE = "network_timeout"
_TIMEOUT_MESSAGE = "The network operation timed out."
_CANCELLED_CODE = "interaction_cancelled"
_CANCELLED_MESSAGE = "The interaction was cancelled."


def classify_transport_failure(
    error: BaseException,
    machine: InteractionTerminalMachine,
) -> ModelInteractionError:
    """Map one transport failure onto a stable category and terminal state.

    An existing network or timeout ``ModelInteractionError`` is preserved and
    fails the interaction. An existing cancellation error, or
    ``asyncio.CancelledError``, cancels the interaction. ``TimeoutError``
    becomes ``network_timeout``. ``OSError`` becomes ``network_error``. The
    public message does not include the original exception text.

    Args:
        error: Failure raised by transport.
        machine: Terminal machine for this interaction.

    Returns:
        The classified interaction error.

    Raises:
        TypeError: If an argument has an invalid type, or the failure is not a
            transport failure this classifier owns.
    """
    error_value = cast(object, error)
    machine_value = cast(object, machine)
    if not isinstance(error_value, BaseException):
        raise TypeError("error must be a BaseException.")
    if not isinstance(machine_value, InteractionTerminalMachine):
        raise TypeError("machine must be an InteractionTerminalMachine.")
    if isinstance(error_value, ModelInteractionError):
        return _finish_known(error_value, machine_value)
    if isinstance(error_value, asyncio.CancelledError):
        machine_value.cancel()
        return _classified(
            _CANCELLATION, _CANCELLED_CODE, _CANCELLED_MESSAGE, error_value
        )
    if isinstance(error_value, TimeoutError):
        machine_value.fail()
        return _classified(_TIMEOUT, _TIMEOUT_CODE, _TIMEOUT_MESSAGE, error_value)
    if isinstance(error_value, OSError):
        machine_value.fail()
        return _classified(_NETWORK, _NETWORK_CODE, _NETWORK_MESSAGE, error_value)
    raise TypeError("error is not a classified transport failure.")


def _finish_known(
    error: ModelInteractionError,
    machine: InteractionTerminalMachine,
) -> ModelInteractionError:
    """Preserve a transport error and record the matching terminal state."""
    if error.category == _CANCELLATION:
        machine.cancel()
        return error
    if error.category in (_NETWORK, _TIMEOUT):
        machine.fail()
        return error
    raise TypeError("error is not a classified transport failure.")


def _classified(
    category: ErrorCategory,
    code: str,
    message: str,
    cause: BaseException,
) -> ModelInteractionError:
    """Build one stable transport error without copying the cause text."""
    return ModelInteractionError(
        category=category,
        phase=_TRANSPORT,
        code=code,
        message=message,
        cause=cause,
    )
