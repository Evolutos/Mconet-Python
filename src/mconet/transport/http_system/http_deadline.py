"""Deadline gate for one HTTP attempt."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.timestamp import Timestamp

_TIMEOUT_CATEGORY = ErrorCategory(OpenIdentifier("timeout"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_DEADLINE_EXCEEDED_CODE = "deadline_exceeded"
_DEADLINE_EXCEEDED_MESSAGE = "HTTP deadline expired."


def ensure_http_deadline(
    deadline: Timestamp | None,
    now: Callable[[], Timestamp],
) -> None:
    """Stop an attempt when the absolute deadline has been reached.

    ``None`` means the caller set no deadline. A deadline equal to or earlier
    than ``now()`` fails as a timeout. The failure is not a caller
    cancellation. The function does not sleep, read a system clock itself, or
    open a connection; the supplied clock decides the current instant.

    Args:
        deadline: Absolute UTC deadline, or ``None``.
        now: Zero-argument clock that returns the current UTC timestamp.

    Raises:
        TypeError: If ``deadline`` or the clock result is not a
            :class:`Timestamp`, or ``now`` is not callable.
        ModelInteractionError: If the deadline has expired. The stable code is
            ``deadline_exceeded`` and the category is ``timeout``.
    """
    candidate = cast(object, deadline)
    if candidate is not None and not isinstance(candidate, Timestamp):
        raise TypeError("deadline must be a Timestamp or None.")
    clock = cast(object, now)
    if not callable(clock):
        raise TypeError("now must be callable.")
    if candidate is None:
        return

    current = cast(object, now())
    if not isinstance(current, Timestamp):
        raise TypeError("now must return a Timestamp.")
    # Equality is expiry. A deadline in the future is still usable and does
    # not become a cancellation.
    if current >= candidate:
        raise _deadline_exceeded_error()


def _deadline_exceeded_error() -> ModelInteractionError:
    """Create the timeout failure for one expired deadline.

    Returns:
        A transport timeout that does not include the deadline text.
    """
    return ModelInteractionError(
        category=_TIMEOUT_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_DEADLINE_EXCEEDED_CODE,
        message=_DEADLINE_EXCEEDED_MESSAGE,
    )
