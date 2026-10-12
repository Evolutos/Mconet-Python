"""Transport failures classify as network, timeout, or cancellation."""

from __future__ import annotations

import asyncio

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._transport_failure_classification import (
    classify_transport_failure,
)

_HOST = "mconet-test-bearer-token-not-secret"


def test_network_timeout_and_cancel_are_distinct() -> None:
    """Verify the three transport failure classes do not share a code."""
    network = classify_transport_failure(
        ConnectionError(_HOST),
        InteractionTerminalMachine(),
    )
    timeout = classify_transport_failure(
        TimeoutError(_HOST),
        InteractionTerminalMachine(),
    )
    cancelled_machine = InteractionTerminalMachine()
    cancelled = classify_transport_failure(
        asyncio.CancelledError(),
        cancelled_machine,
    )

    assert network.code == "network_error"
    assert network.category == ErrorCategory(OpenIdentifier("network"))
    assert timeout.code == "network_timeout"
    assert timeout.category == ErrorCategory(OpenIdentifier("timeout"))
    assert cancelled.code == "interaction_cancelled"
    assert cancelled.category == ErrorCategory(OpenIdentifier("cancellation"))
    assert network.phase == timeout.phase == cancelled.phase
    assert cancelled_machine.state is not None
    assert cancelled_machine.state.cancelled is True
    assert _HOST not in network.message
    assert _HOST not in timeout.message
    assert isinstance(network.cause, ConnectionError)


def test_known_deadline_error_is_preserved_as_timeout() -> None:
    """Verify an existing deadline error is not rewritten as a network error."""
    expected = ModelInteractionError(
        ErrorCategory(OpenIdentifier("timeout")),
        InteractionPhase(OpenIdentifier("transport")),
        "deadline_exceeded",
        "HTTP deadline expired.",
    )
    machine = InteractionTerminalMachine()

    assert classify_transport_failure(expected, machine) is expected
    assert machine.state is not None
    assert machine.state.failed is True
