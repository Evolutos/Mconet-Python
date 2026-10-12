"""Runtime boundary that normalizes an unknown interaction failure."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_INTERNAL = ErrorCategory(OpenIdentifier("internal"))
_UNKNOWN_CODE = "unknown_interaction_failure"
_UNKNOWN_MESSAGE = "The interaction failed unexpectedly."

_T = TypeVar("_T")


def guard_unknown_exception(
    operation: Callable[[], _T],
    *,
    phase: InteractionPhase,
) -> _T:
    """Run one interaction step and normalize an unknown failure.

    A ``ModelInteractionError`` is re-raised by identity. Any other
    ``Exception`` becomes one stable error whose message does not include the
    original text. The original exception is retained as ``cause``.
    ``BaseException`` values that are not ``Exception``, including
    ``KeyboardInterrupt`` and ``SystemExit``, propagate unchanged.

    Args:
        operation: One interaction step.
        phase: Phase in which an unknown failure becomes final.

    Returns:
        The value returned by that single call.

    Raises:
        TypeError: If an argument has an invalid type.
        ModelInteractionError: If the step fails. An unknown failure uses
            ``unknown_interaction_failure``.
        BaseException: If the step raises a non-Exception base exception.
    """
    operation_value = cast(object, operation)
    phase_value = cast(object, phase)
    if not isinstance(operation_value, Callable):
        raise TypeError("operation must be callable.")
    if not isinstance(phase_value, InteractionPhase):
        raise TypeError("phase must be an InteractionPhase.")
    checked = cast(Callable[[], _T], operation_value)
    try:
        return checked()
    except ModelInteractionError:
        raise
    except Exception as error:
        raise ModelInteractionError(
            category=_INTERNAL,
            phase=phase_value,
            code=_UNKNOWN_CODE,
            message=_UNKNOWN_MESSAGE,
            cause=error,
        ) from error
