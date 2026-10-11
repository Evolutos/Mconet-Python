"""Runtime scheduling for one interaction's cancellation signal."""

from __future__ import annotations

from typing import cast

from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)


def resolve_cancellation_signal(
    configuration: ResolvedInteractionConfiguration,
) -> CancellationSignal | None:
    """Return the caller signal for this interaction, or None.

    The returned object is the signal already stored on the resolved
    configuration. Later stages observe that same object, so a cancellation the
    caller performs is visible to this interaction. The function does not
    subscribe, request cancellation, copy another interaction's state, or
    replace an absent signal with a process-wide one.

    Args:
        configuration: The resolved configuration for this interaction alone.

    Returns:
        The interaction's caller signal, or None when the caller supplied none.

    Raises:
        TypeError: If ``configuration`` is not the resolved configuration type.
    """
    candidate = cast(object, configuration)
    # A client options object must not be read as if it were this interaction's
    # resolved configuration.
    if not isinstance(candidate, ResolvedInteractionConfiguration):
        raise TypeError("configuration must be ResolvedInteractionConfiguration.")
    # Identity, not a copy, is what lets the caller's later cancel propagate.
    # None remains none so two interactions cannot share a default signal.
    return candidate.cancellation_signal
