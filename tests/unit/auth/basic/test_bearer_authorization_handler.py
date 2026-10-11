"""Tests for the bearer authorization handler."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.bearer_authorization import BearerAuthorization
from mconet.auth.basic.bearer_authorization_handler import BearerAuthorizationHandler
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

_PLACEHOLDER = "mconet-test-bearer-token-not-secret"


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
    """Build non-sensitive facts for an unsigned bearer attempt."""
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
        query=QueryParameters(),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def test_bearer_handler_appends_only_the_bearer_header() -> None:
    """Verify the token is placed in Authorization and the payload stays put."""
    authorization = BearerAuthorization(
        FixedCredentialSource(SecretValue(_PLACEHOLDER))
    )
    handler = BearerAuthorizationHandler()
    request = _request()
    url = request.url
    query = request.query
    body = request.body

    def assert_request(actual: MutableTransportRequest) -> None:
        """Require the bearer header and the original payload identity."""
        assert actual.url is url
        assert actual.query is query
        assert actual.body is body
        assert actual.headers.values == (
            HeaderField("X-Trace", "trace-value"),
            HeaderField("Authorization", f"Bearer {_PLACEHOLDER}"),
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


def test_bearer_handler_rejects_a_non_text_credential_without_copying_it() -> None:
    """Verify a byte token does not become a header or an error payload."""
    marker = b"mconet-test-bytes-not-secret"
    authorization = BearerAuthorization(
        FixedCredentialSource(SecretValue(Bytes(marker)))
    )
    request = _request()
    body = request.body

    async def apply() -> None:
        await BearerAuthorizationHandler().apply(
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


def test_bearer_handler_rejects_a_control_in_the_token_without_copying_it() -> None:
    """Verify a control in the token is not written and is not copied into the error."""
    authorization = BearerAuthorization(
        FixedCredentialSource(SecretValue(f"{_PLACEHOLDER}\r\n"))
    )
    request = _request()
    headers = request.headers

    async def apply() -> None:
        await BearerAuthorizationHandler().apply(
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
        raise AssertionError("Expected a control character in the token to fail.")

    assert request.headers is headers
