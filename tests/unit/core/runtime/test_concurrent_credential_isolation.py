"""Concurrent credential reads do not cross interactions."""

from __future__ import annotations

import asyncio
from types import MappingProxyType

from mconet.core.domain import (
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    Timestamp,
    UriValue,
)
from mconet.core.domain.extensions import Extensions
from mconet.core.runtime._credential_read import read_interaction_credential
from mconet.core.spi import AuthorizationContext, CredentialValue


class _Target:
    """Target shared as non-secret authorization context."""

    def __init__(self) -> None:
        """Store one named model target."""
        self.service_id = OpenIdentifier("service.vendor")
        self.protocol_id = OpenIdentifier("protocol.vendor")
        self.model: ModelDescriptor = NamedModel("requested-model")
        self.deployment_id = None
        self.extensions: Extensions = MappingProxyType({})


class _Credential:
    """Credential whose identity is the interaction index."""

    def __init__(self, index: int) -> None:
        """Store the non-secret kind and the interaction index."""
        self.kind = OpenIdentifier("credential.token")
        self.index = index

    def reveal(self, consumer: object) -> int:
        """Return the index only when a caller asks to reveal it."""
        del consumer
        return self.index


class _Source:
    """Source that returns one fixed credential."""

    def __init__(self, credential: _Credential) -> None:
        """Store the credential owned by one interaction."""
        self._credential = credential

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Return this interaction's credential after yielding once."""
        del context
        await asyncio.sleep(0)
        return self._credential


class _Authorization:
    """Decision bound to one credential source."""

    def __init__(self, source: _Source) -> None:
        """Store the kind and the source."""
        self.kind = OpenIdentifier("authorization.bearer")
        self.credential_source = source


async def _read(index: int, context: AuthorizationContext) -> int:
    """Read the credential for one interaction and return its index."""
    credential = _Credential(index)
    value = await read_interaction_credential(
        _Authorization(_Source(credential)),
        context,
    )
    assert value is credential
    return credential.index


def test_concurrent_credentials_do_not_cross() -> None:
    """Verify one hundred dynamic reads stay with their own sources."""
    context = AuthorizationContext(
        "interaction-shared-facts",
        _Target(),
        UriValue("https://example.test/v1", True),
        OpenIdentifier("http"),
        Timestamp(1_700_000_000, 0),
        "none",
    )

    async def _all() -> list[int]:
        return list(
            await asyncio.gather(*(_read(index, context) for index in range(100)))
        )

    assert asyncio.run(_all()) == list(range(100))
