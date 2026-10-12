"""Builtin-owned components are closed with the client."""

from __future__ import annotations

import asyncio
from typing import cast

from mconet.client._builtin_component_release import release_builtin_client_components
from mconet.core.spi import (
    ComponentDescriptor,
    RuntimeComponents,
    Transport,
)


class _BuiltinResource:
    """SDK-owned resource whose close can be counted."""

    def __init__(self) -> None:
        """Store metadata and a close counter."""
        self.descriptor = ComponentDescriptor("transport", "1.0.0", "builtin")
        self.calls: list[str] = []

    async def close(self) -> None:
        """Record one close call."""
        self.calls.append("close")

    async def send(self, *values: object) -> object:
        """Satisfy transport presence without sending."""
        del values
        return None


def test_builtin_component_is_closed_with_the_client_release() -> None:
    """Verify an SDK-owned resource is closed and a second release repeats."""
    resource = _BuiltinResource()
    defaults = RuntimeComponents(transport=cast(Transport, resource))

    asyncio.run(release_builtin_client_components(defaults, None))
    asyncio.run(release_builtin_client_components(defaults, None))

    assert resource.calls == ["close", "close"]
