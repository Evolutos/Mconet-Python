"""OpenAI-compatible client defaults come from the existing binding."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from types import MappingProxyType

from mconet.auth.basic import NoAuthorization
from mconet.client import make_openai_compatible
from mconet.client.text_request import model_request_from_text
from mconet.core.domain import (
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import InteractionOptions
from mconet.testing import MockHttpResponseScript, MockHttpServer


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural chat-completions target."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Explicit endpoint and no-authorization decision."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_openai_compatible_client_uses_the_binding_and_access_default() -> None:
    """Verify the factory stores target and access and sends through the binding."""
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )
    response = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ]
    }
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=json.dumps(response).encode("utf-8"),
    )
    with MockHttpServer((script,)) as server:
        access: ServiceAccess = _Access(server.uri, NoAuthorization())
        client = make_openai_compatible(target, access)
        assert client.configuration.default_target is target
        assert client.configuration.default_service_access is access
        components = client.configuration.components
        assert components is not None
        assert components.payload_encoder is None
        assert components.transport is None
        assert components.model_integration_resolver is not None
        request = model_request_from_text(target, "Hello")
        assert request.service_access is None
        output = asyncio.run(client.interact(request, InteractionOptions()))
        recorded = server.requests

    assert output.stop_reason == "stop"
    assert len(recorded) == 1
    assert b"Hello" in recorded[0].body
    assert b"vendor-model" in recorded[0].body
    asyncio.run(client.close())
    try:
        asyncio.run(client.interact(request, InteractionOptions()))
    except ModelInteractionError as error:
        assert error.code == "client_closed"
    else:
        raise AssertionError("Expected a closed client to reject the request.")
