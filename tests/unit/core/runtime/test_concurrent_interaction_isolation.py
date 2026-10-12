"""One hundred concurrent mock interactions do not share outcomes."""

from __future__ import annotations

import asyncio

from mconet.core.domain import (
    Bytes,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    UriValue,
)
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.spi import (
    ComponentDescriptor,
    TransportBody,
    TransportContext,
    TransportOutcome,
    TransportRequest,
    TransportResponse,
    TransportResponseMetadata,
)
from mconet.testing import MockTransport


async def _one(index: int) -> tuple[str, bytes]:
    """Send one private mock response and complete that interaction only."""
    machine = InteractionTerminalMachine()
    interaction_id = f"interaction-{index}"
    response = TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier("success")),
            Headers(),
        ),
        Bytes(str(index).encode("ascii")),
    )
    transport = MockTransport(
        ComponentDescriptor(f"transport-{index}", "1.0.0", "application"),
        response,
    )
    result = await transport.send(
        TransportRequest(
            "POST",
            UriValue("https://example.test/v1", True),
            Headers(),
            QueryParameters(),
            TransportBody(Bytes(b"{}"), MediaType("application", "json")),
        ),
        TransportContext(
            interaction_id,
            ResolvedInteractionResourceLimits(100, 200, 300),
        ),
    )
    machine.complete()
    assert machine.state is not None
    assert machine.state.completed is True
    return interaction_id, bytes(result.body)


async def _all() -> list[tuple[str, bytes]]:
    """Run the one hundred interactions together."""
    return list(await asyncio.gather(*(_one(index) for index in range(100))))


def test_one_hundred_concurrent_interactions_stay_isolated() -> None:
    """Verify concurrent mock sends keep their own ids and response bodies."""
    results = asyncio.run(_all())

    assert [item[0] for item in results] == [
        f"interaction-{index}" for index in range(100)
    ]
    assert [item[1] for item in results] == [
        str(index).encode("ascii") for index in range(100)
    ]
