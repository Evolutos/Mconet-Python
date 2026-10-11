"""Runtime scheduling for one interaction's absolute transport deadline."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.domain.duration import Duration
from mconet.core.domain.timestamp import Timestamp
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.core.spi.transport_context import TransportContext

_NANOSECONDS_PER_SECOND = 1_000_000_000


def resolve_transport_context(
    *,
    interaction_id: str,
    configuration: ResolvedInteractionConfiguration,
    cancellation: CancellationSignal | None,
    timeout: Duration | None,
    now: Callable[[], Timestamp],
) -> TransportContext:
    """Compute one absolute deadline and store it on a transport context.

    A timeout is added to a single clock reading. The resulting timestamp is
    stored on the context and is not recomputed when the clock later moves.
    No timeout stores no deadline and does not read the clock. The context also
    carries this interaction's id, resolved byte limits, and the cancellation
    signal already selected for it.

    Args:
        interaction_id: Identifier of the interaction that will own the context.
        configuration: Resolved configuration whose resource limits are copied
            by identity onto the context.
        cancellation: The caller signal for this interaction, or None.
        timeout: Relative timeout to turn into one absolute deadline, or None.
        now: Zero-argument clock used for that single reading.

    Returns:
        A transport context whose deadline stays at the computed instant.

    Raises:
        TypeError: If an argument has an invalid runtime type.
        ValueError: If ``timeout`` is negative.
    """
    interaction_value = cast(object, interaction_id)
    configuration_value = cast(object, configuration)
    timeout_value = cast(object, timeout)
    clock = cast(object, now)
    if not isinstance(interaction_value, str):
        raise TypeError("interaction_id must be a string.")
    if not isinstance(configuration_value, ResolvedInteractionConfiguration):
        raise TypeError("configuration must be ResolvedInteractionConfiguration.")
    if timeout_value is not None and not isinstance(timeout_value, Duration):
        raise TypeError("timeout must be a Duration or None.")
    if not callable(clock):
        raise TypeError("now must be callable.")
    # A negative timeout is not a deadline. Reject it before reading the clock
    # so a failed call does not consume the single allowed time sample.
    if timeout_value is not None and timeout_value.total_nanoseconds < 0:
        raise ValueError("timeout must not be negative.")

    deadline = None if timeout_value is None else _absolute_deadline(timeout_value, now)
    # Resource limits and cancellation are stored by identity. The deadline
    # field is the one absolute instant this interaction will keep using.
    return TransportContext(
        interaction_id=interaction_id,
        resource_limits=configuration.resource_limits,
        deadline=deadline,
        cancellation=cancellation,
    )


def _absolute_deadline(timeout: Duration, now: Callable[[], Timestamp]) -> Timestamp:
    """Add one timeout to one clock reading."""
    # One call fixes the deadline. Later clock movement must not change it.
    start = now()
    start_value = cast(object, start)
    if not isinstance(start_value, Timestamp):
        raise TypeError("now must return a Timestamp.")
    if timeout.total_nanoseconds == 0:
        # A zero timeout is already due at the sampled instant. Reuse that
        # object instead of allocating an equal replacement.
        return start_value

    start_nanoseconds = (
        start_value.epoch_seconds * _NANOSECONDS_PER_SECOND + start_value.nanosecond
    )
    # Integer addition avoids float rounding. Floor division keeps the
    # fractional field inside the timestamp's canonical range.
    total = start_nanoseconds + timeout.total_nanoseconds
    epoch_seconds, nanosecond = divmod(total, _NANOSECONDS_PER_SECOND)
    return Timestamp(epoch_seconds, nanosecond)
