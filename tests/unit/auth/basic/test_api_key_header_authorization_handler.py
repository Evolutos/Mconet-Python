"""Tests for the header API key authorization handler."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.api_key_header_authorization_handler import (
    ApiKeyHeaderAuthorizationHandler,
)
from mconet.auth.basic.dynamic_credential_source import DynamicCredentialSource
from mconet.auth.basic.fixed_credential_source import FixedCredentialSource
from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.core.domain import (
    Bytes,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    SecretValue,
    Timestamp,
    UriValue,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningRequirement,
    MutableTransportRequest,
    TransportBody,
)
from mconet.testing import AuthorizationHandlerContractSuite

_PLACEHOLDER = "mconet-test-api-key-not-secret"


def _empty_extensions() -> Extensions:
    """Create independent extension storage for one target fixture."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target for one authorization context."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def _context() -> AuthorizationContext:
    """Build non-sensitive facts for an unsigned API key attempt."""
    return AuthorizationContext(
        interaction_id="interaction-1",
        target=cast(
            ModelTarget,
            _Target(
                OpenIdentifier("service.example"),
                OpenIdentifier("protocol.example"),
                NamedModel("model-example"),
            ),
        ),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_800_000_000, 0),
        body_signing_mode="none",
    )


def _request() -> MutableTransportRequest:
    """Build one open request with a payload the handler must not replace."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers((HeaderField("X-Trace", "trace-value"),)),
        query=QueryParameters((QueryParameter("region", "east"),)),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def test_api_key_handler_appends_only_the_configured_header() -> None:
    """Verify the payload, URL, and query stay in place while one header is added."""
    source = FixedCredentialSource(SecretValue(_PLACEHOLDER))
    authorization = ApiKeyHeaderAuthorization("X-Api-Key", "Key ", source)
    handler = ApiKeyHeaderAuthorizationHandler()
    request = _request()
    url = request.url
    query = request.query
    body = request.body

    def assert_request(actual: MutableTransportRequest) -> None:
        """Require one appended header and the original payload identity."""
        assert actual.url is url
        assert actual.query is query
        assert actual.body is body
        assert actual.headers.values == (
            HeaderField("X-Trace", "trace-value"),
            HeaderField("X-Api-Key", f"Key {_PLACEHOLDER}"),
        )
        assert actual.is_frozen is False

    asyncio.run(
        AuthorizationHandlerContractSuite(handler).assert_apply(
            authorization,
            _context(),
            request,
            assertion=assert_request,
        )
    )
    assert isinstance(handler, AuthorizationHandler)
    assert handler.supports(authorization, BodySigningRequirement()) == frozenset(
        {"none"}
    )
    assert handler.supports(NoAuthorization(), BodySigningRequirement()) == frozenset()


def test_api_key_handler_rejects_a_non_text_credential_without_copying_it() -> None:
    """Verify a byte credential does not become a header or an error payload."""
    marker = b"mconet-test-bytes-not-secret"
    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "",
        FixedCredentialSource(SecretValue(Bytes(marker))),
    )
    request = _request()
    body = request.body

    async def apply() -> None:
        await ApiKeyHeaderAuthorizationHandler().apply(
            authorization,
            _context(),
            request,
        )

    try:
        asyncio.run(apply())
    except TypeError as error:
        assert "must be text" in str(error)
        assert "mconet-test-bytes-not-secret" not in str(error)
    else:
        raise AssertionError("Expected a non-text credential to fail.")

    assert request.body is body
    assert request.headers.values == (HeaderField("X-Trace", "trace-value"),)


def test_api_key_handler_rejects_an_illegal_header_name_before_credentials() -> None:
    """Verify a colon in the name fails without reading the key."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_PLACEHOLDER)

    authorization = ApiKeyHeaderAuthorization(
        "X:Api-Key",
        "",
        DynamicCredentialSource(provider),
    )
    request = _request()
    headers = request.headers

    async def apply() -> None:
        await ApiKeyHeaderAuthorizationHandler().apply(
            authorization,
            _context(),
            request,
        )

    try:
        asyncio.run(apply())
    except ModelInteractionError as error:
        assert error.code == "invalid_authorization_header_name"
        assert "X:Api-Key" not in str(error)
    else:
        raise AssertionError("Expected an illegal header name to fail.")

    assert calls == []
    assert request.headers is headers


def test_api_key_handler_rejects_a_control_prefix_before_credentials() -> None:
    """Verify a CR or LF in the prefix fails without reading the key."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_PLACEHOLDER)

    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "\r\n",
        DynamicCredentialSource(provider),
    )
    request = _request()
    headers = request.headers

    async def apply() -> None:
        await ApiKeyHeaderAuthorizationHandler().apply(
            authorization,
            _context(),
            request,
        )

    try:
        asyncio.run(apply())
    except ModelInteractionError as error:
        assert error.code == "invalid_authorization_header_value"
        assert _PLACEHOLDER not in str(error)
    else:
        raise AssertionError("Expected a control character in the prefix to fail.")

    assert calls == []
    assert request.headers is headers


def test_api_key_handler_rejects_a_control_in_the_key_without_copying_it() -> None:
    """Verify a control in the key is not written and is not copied into the error."""
    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "",
        FixedCredentialSource(SecretValue(f"{_PLACEHOLDER}\n")),
    )
    request = _request()
    headers = request.headers

    async def apply() -> None:
        await ApiKeyHeaderAuthorizationHandler().apply(
            authorization,
            _context(),
            request,
        )

    try:
        asyncio.run(apply())
    except ModelInteractionError as error:
        assert error.code == "invalid_authorization_header_value"
        assert _PLACEHOLDER not in str(error)
    else:
        raise AssertionError("Expected a control character in the key to fail.")

    assert request.headers is headers
