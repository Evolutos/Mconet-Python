"""Normalization of platform network timeouts."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier

_TIMEOUT_CATEGORY = ErrorCategory(OpenIdentifier("timeout"))
_TRANSPORT_PHASE = InteractionPhase(OpenIdentifier("transport"))
_NETWORK_TIMEOUT_CODE = "network_timeout"
_NETWORK_TIMEOUT_MESSAGE = "HTTP network operation timed out."


def normalize_http_network_timeout(error: BaseException) -> ModelInteractionError:
    """Map one platform timeout onto a stable transport timeout.

    ``TimeoutError`` includes ``socket.timeout``. The result uses category
    ``timeout``, phase ``transport``, and code ``network_timeout``, which is
    distinct from a caller deadline. The platform message is not copied,
    because it can contain the destination. Other exceptions are not treated
    as timeouts.

    Args:
        error: Exception raised by the platform network stack.

    Returns:
        A timeout whose cause is not the platform exception.

    Raises:
        TypeError: If ``error`` is not a ``TimeoutError``.
    """
    candidate = cast(object, error)
    if not isinstance(candidate, TimeoutError):
        raise TypeError("error must be a TimeoutError.")
    # Drop the platform exception. Its text is not a stable code and may name
    # the host or a proxy credential.
    return ModelInteractionError(
        category=_TIMEOUT_CATEGORY,
        phase=_TRANSPORT_PHASE,
        code=_NETWORK_TIMEOUT_CODE,
        message=_NETWORK_TIMEOUT_MESSAGE,
    )
