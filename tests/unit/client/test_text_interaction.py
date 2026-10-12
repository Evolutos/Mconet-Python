"""Text convenience calls delegate to the unary interact entry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from mconet.client.model_client import ModelClient
from mconet.core.domain import (
    Extensions,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
)
from mconet.core.spi import ModelClientConfiguration


def _empty_extensions() -> Extensions:
    """Return one independent empty extension mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target for one text convenience call."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_text_api_uses_interact_after_the_client_is_closed() -> None:
    """Verify the text entry reaches interact and does not send on its own."""
    client = ModelClient(ModelClientConfiguration())
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    asyncio.run(client.close())
    try:
        asyncio.run(client.interact_text(target, "Hello"))
    except ModelInteractionError as error:
        assert error.code == "client_closed"
    else:
        raise AssertionError("Expected the text entry to delegate to interact.")
