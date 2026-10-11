"""Tests for the no-authorization handler."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.auth.basic.no_authorization_handler import NoAuthorizationHandler
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
    Timestamp,
    UriValue,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningMode,
    BodySigningRequirement,
    CredentialValue,
    MutableTransportRequest,
    TransportBody,
)
from mconet.testing import AuthorizationHandlerContractSuite


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


class _IdleCredentialSource:
    """Credential source that fails if a no-auth handler resolves it."""

    def __init__(self) -> None:
        """Start with no resolution attempts."""
        self.calls = 0

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Fail if no-authorization handling tries to read a credential."""
        del context
        self.calls += 1
        raise AssertionError("no-authorization handler resolved a credential")


def _context() -> AuthorizationContext:
    """Build non-sensitive facts for an unsigned authorization attempt."""
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
    """Build one open request whose fields must survive no-authorization."""
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


def test_no_authorization_handler_matches_only_the_unsigned_decision() -> None:
    """Verify other decisions and required signing do not match."""
    handler = NoAuthorizationHandler()
    source = _IdleCredentialSource()
    other = ApiKeyHeaderAuthorization("X-Api-Key", "", source)
    signing = BodySigningRequirement(
        required=True,
        acceptable_modes=(cast(BodySigningMode, "unsigned_payload"),),
    )

    assert isinstance(handler, AuthorizationHandler)
    assert handler.supports(NoAuthorization(), BodySigningRequirement()) == frozenset(
        {"none"}
    )
    assert handler.supports(other, BodySigningRequirement()) == frozenset()
    assert handler.supports(NoAuthorization(), signing) == frozenset()
    assert source.calls == 0


def test_no_authorization_handler_leaves_the_request_unchanged() -> None:
    """Verify apply does not replace, freeze, or read a credential."""
    handler = NoAuthorizationHandler()
    request = _request()
    url = request.url
    headers = request.headers
    query = request.query
    body = request.body

    def assert_request(actual: MutableTransportRequest) -> None:
        """Require every mutable field to keep its original identity."""
        assert actual.url is url
        assert actual.headers is headers
        assert actual.query is query
        assert actual.body is body
        assert actual.is_frozen is False

    asyncio.run(
        AuthorizationHandlerContractSuite(handler).assert_apply(
            NoAuthorization(),
            _context(),
            request,
            assertion=assert_request,
        )
    )


def test_no_authorization_handler_rejects_another_decision_without_credentials() -> (
    None
):
    """Verify a credential-bearing decision is not read or applied."""
    source = _IdleCredentialSource()
    authorization = ApiKeyHeaderAuthorization("X-Api-Key", "", source)
    request = _request()
    headers = request.headers

    async def apply() -> None:
        await NoAuthorizationHandler().apply(authorization, _context(), request)

    try:
        asyncio.run(apply())
    except ModelInteractionError as error:
        assert error.code == "unsupported_authorization"
        assert str(error.category.id) == "authentication"
        assert "X-Api-Key" not in error.message
    else:
        raise AssertionError("Expected an unsupported authorization failure.")

    assert source.calls == 0
    assert request.headers is headers
    assert request.is_frozen is False
