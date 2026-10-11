"""Tests for per-interaction cancellation signal scheduling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from mconet.core.domain import (
    CompatibilityPolicy,
    Extensions,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
)
from mconet.core.runtime._cancellation_resolution import resolve_cancellation_signal
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.testing import ControllableCancellationSignal


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


class _CountingSignal(ControllableCancellationSignal):
    """Count subscriptions so the scheduler can be shown not to register one."""

    def __init__(self) -> None:
        """Start from the controllable signal with a zero subscription count."""
        super().__init__()
        # The count is test state. The scheduler must leave it at zero.
        self.subscribe_calls = 0

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Record one subscription and preserve the base signal behavior."""
        self.subscribe_calls += 1
        return super().subscribe(callback)


def _configuration(
    signal: ControllableCancellationSignal | None,
) -> ResolvedInteractionConfiguration:
    """Build a resolved configuration that stores only the given signal."""
    # Target, policy, and limits are present so the carrier is complete. This
    # stage reads the signal and does not interpret those other fields.
    return ResolvedInteractionConfiguration(
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("protocol.vendor"),
            NamedModel("vendor-model"),
        ),
        None,
        CompatibilityPolicy(OpenIdentifier("compatible")),
        ResolvedInteractionResourceLimits(100, 200, 300),
        signal,
    )


def test_caller_cancellation_propagates_through_the_same_signal() -> None:
    """Verify the scheduled signal is the caller's object."""
    signal = _CountingSignal()
    scheduled = resolve_cancellation_signal(_configuration(signal))

    # The later stage sees the caller's transition because no copy was made
    # and no subscription was registered by the scheduler itself.
    assert scheduled is signal
    assert signal.subscribe_calls == 0
    signal.cancel("stopped")
    assert scheduled is not None
    assert scheduled.is_cancelled is True
    assert scheduled.reason == "stopped"


def test_cancellation_state_is_not_shared_between_interactions() -> None:
    """Verify one interaction's cancellation does not change another."""
    first_signal = ControllableCancellationSignal()
    second_signal = ControllableCancellationSignal()
    first = resolve_cancellation_signal(_configuration(first_signal))
    second = resolve_cancellation_signal(_configuration(second_signal))
    absent = resolve_cancellation_signal(_configuration(None))

    assert first is not None
    first_signal.cancel("first-only")

    # The second interaction keeps its own active signal. An interaction with
    # no caller signal does not inherit the cancelled one.
    assert first.is_cancelled is True
    assert second is not None
    assert second.is_cancelled is False
    assert second.reason is None
    assert absent is None
