"""A per-call component override leaves the reusable client configuration."""

from __future__ import annotations

import asyncio

from examples.per_call_override import run_per_call_override


def test_per_call_override_does_not_change_the_client() -> None:
    """Verify the override encoder runs and the client encoder stays stored."""
    unchanged, client_calls, override_calls = asyncio.run(run_per_call_override())
    assert unchanged is True
    assert client_calls == 0
    assert override_calls == 1
