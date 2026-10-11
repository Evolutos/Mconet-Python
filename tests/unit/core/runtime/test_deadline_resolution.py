"""Tests that a transport deadline is computed once."""

from __future__ import annotations

from dataclasses import dataclass, field

from mconet.core.domain import (
    CompatibilityPolicy,
    Duration,
    Extensions,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
    Timestamp,
)
from mconet.core.runtime._deadline_resolution import resolve_transport_context
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.testing import ControllableCancellationSignal, FakeClock


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep one fixture from mutating another fixture's fields.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target required by a resolved configuration."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _CountingClock:
    """Count how many times the deadline scheduler reads the clock."""

    def __init__(self, clock: FakeClock) -> None:
        """Wrap one fake clock."""
        self._clock = clock
        # The scheduler may read the clock only while computing a deadline.
        self.calls = 0

    def now(self) -> Timestamp:
        """Return the current instant and record the read."""
        self.calls += 1
        return self._clock.now()


def _configuration() -> ResolvedInteractionConfiguration:
    """Return a resolved configuration with fixed resource limits."""
    return ResolvedInteractionConfiguration(
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("protocol.vendor"),
            NamedModel("vendor-model"),
        ),
        None,
        CompatibilityPolicy(OpenIdentifier("compatible")),
        ResolvedInteractionResourceLimits(100, 200, 300),
        None,
    )


def test_timeout_is_sampled_once_and_stays_on_the_context() -> None:
    """Verify a later clock advance does not recompute the deadline."""
    clock = FakeClock(Timestamp(1_700_000_000, 900_000_000))
    counted = _CountingClock(clock)
    signal = ControllableCancellationSignal()
    configuration = _configuration()

    context = resolve_transport_context(
        interaction_id="interaction-1",
        configuration=configuration,
        cancellation=signal,
        timeout=Duration(200_000_000),
        now=counted.now,
    )
    clock.advance(Duration(5_000_000_000))

    # The context keeps the instant from the single sample, including the
    # nanosecond carry into the next second.
    assert counted.calls == 1
    assert context.deadline == Timestamp(1_700_000_001, 100_000_000)
    assert context.interaction_id == "interaction-1"
    assert context.resource_limits is configuration.resource_limits
    assert context.cancellation is signal


def test_absent_timeout_does_not_read_the_clock() -> None:
    """Verify no deadline is stored when the caller set no timeout."""
    clock = FakeClock(Timestamp(10, 0))
    counted = _CountingClock(clock)

    context = resolve_transport_context(
        interaction_id="interaction-2",
        configuration=_configuration(),
        cancellation=None,
        timeout=None,
        now=counted.now,
    )

    assert counted.calls == 0
    assert context.deadline is None


def test_negative_timeout_fails_before_reading_the_clock() -> None:
    """Verify a negative timeout is rejected without a time sample."""
    clock = FakeClock(Timestamp(10, 0))
    counted = _CountingClock(clock)

    try:
        resolve_transport_context(
            interaction_id="interaction-3",
            configuration=_configuration(),
            cancellation=None,
            timeout=Duration(-1),
            now=counted.now,
        )
    except ValueError as error:
        assert "negative" in str(error)
    else:
        raise AssertionError("Expected the action to fail.")

    assert counted.calls == 0
