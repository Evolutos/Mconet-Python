"""Tests that a monitor failure does not replace the interaction result."""

from __future__ import annotations

import asyncio

from mconet.core.domain import OpenIdentifier, Timestamp
from mconet.core.runtime._monitor_failure_isolation import (
    publish_isolated_monitor_chain,
)
from mconet.core.spi import ComponentDescriptor, MonitoringEvent


class _Monitor:
    """Record a call and optionally raise after observing the event."""

    def __init__(
        self,
        name: str,
        log: list[str],
        *,
        error: Exception | None = None,
    ) -> None:
        """Store the name, shared log, and optional failure."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application")
        self.observed_events = None
        self._log = log
        self._name = name
        self._error = error

    async def on_event(self, event: MonitoringEvent) -> None:
        """Record the call, then raise when this monitor is configured to fail."""
        del event
        self._log.append(self._name)
        if self._error is not None:
            raise self._error


def test_monitor_failure_keeps_the_interaction_result() -> None:
    """Verify a failing monitor does not stop later monitors or change the result."""
    event = MonitoringEvent(
        "event-1",
        OpenIdentifier("interaction.failed"),
        "interaction-1",
        None,
        Timestamp(1_700_000_000, 0),
        {"status": "failed"},
        {},
    )
    result = {"output": "kept"}
    failure = RuntimeError("mconet-test-bearer-token-not-secret")
    log: list[str] = []
    returned, failures = asyncio.run(
        publish_isolated_monitor_chain(
            (
                _Monitor("first", log),
                _Monitor("second", log, error=failure),
                _Monitor("third", log),
            ),
            event,
            result,
        )
    )

    assert returned is result
    assert failures == (failure,)
    assert log == ["first", "second", "third"]
    assert "mconet-test-bearer-token-not-secret" not in str(result)
