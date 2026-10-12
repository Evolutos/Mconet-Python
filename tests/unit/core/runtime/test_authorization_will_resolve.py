"""Tests for the authorization.will_resolve monitor event."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError

from mconet.core.domain import (
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameters,
    Timestamp,
    UriValue,
)
from mconet.core.runtime._authorization_will_resolve import (
    publish_authorization_will_resolve,
)
from mconet.core.spi import ComponentDescriptor, TransportBody, TransportRequest
from mconet.testing import StubInteractionMonitor

_BEARER = "mconet-test-bearer-token-not-secret"


def _snapshot() -> TransportRequest:
    """Return a request whose header value and body must not be published."""
    return TransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/chat/completions", True),
        headers=Headers((HeaderField("Authorization", f"Bearer {_BEARER}"),)),
        query=QueryParameters(),
        body=TransportBody(
            Bytes(_BEARER.encode("utf-8")),
            MediaType("application", "json"),
        ),
    )


def _monitor(
    observed: frozenset[OpenIdentifier] | None,
) -> StubInteractionMonitor:
    """Return a recording monitor with the given event filter."""
    return StubInteractionMonitor(
        ComponentDescriptor("monitor", "1.0.0", "application"),
        observed,
    )


def test_monitors_receive_one_frozen_redacted_event() -> None:
    """Verify publication omits secrets and skips an unrelated subscription."""
    interested = _monitor(None)
    unrelated = _monitor(frozenset((OpenIdentifier("interaction.completed"),)))

    event = asyncio.run(
        publish_authorization_will_resolve(
            event_id="event-1",
            interaction_id="interaction-1",
            snapshot=_snapshot(),
            monitors=(interested, unrelated),
            timestamp=Timestamp(1_700_000_000, 0),
        )
    )

    published = json.dumps(event.payload)
    assert event.type == OpenIdentifier("authorization.will_resolve")
    assert interested.events == (event,)
    assert unrelated.events == ()
    assert _BEARER not in published
    assert isinstance(event.payload, dict)
    assert event.payload["header_names"] == ["Authorization"]
    mutation = _capture(lambda: setattr(event, "payload", {}))
    assert isinstance(mutation, FrozenInstanceError)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
