"""The smallest unary text call through the public client API."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from mconet.auth.basic import NoAuthorization
from mconet.client import make_openai_compatible
from mconet.core.domain import (
    Authorization,
    Extensions,
    Headers,
    ModelDescriptor,
    ModelOutput,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    UriValue,
)


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _ChatTarget:
    """Application target for one chat-completions call."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _ChatAccess:
    """Application access that names an endpoint and no authorization."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


async def run_simplest_call(endpoint: UriValue) -> ModelOutput:
    """Send one text prompt with the OpenAI-compatible client preset.

    The example constructs no encoder, decoder, transport, or adapter. Those
    come from the public preset. The caller supplies only the endpoint.

    Args:
        endpoint: Absolute service URI for this call.

    Returns:
        The model output produced by ``interact_text``.
    """
    target: ModelTarget = _ChatTarget(
        OpenIdentifier("service.example"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("example-model"),
    )
    access: ServiceAccess = _ChatAccess(endpoint, NoAuthorization())
    client = make_openai_compatible(target, access)
    try:
        return await client.interact_text(target, "Hello")
    finally:
        await client.close()
