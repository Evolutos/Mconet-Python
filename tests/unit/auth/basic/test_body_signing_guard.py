"""Tests for the shared R1 body-signing guard."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.api_key_header_authorization_handler import (
    ApiKeyHeaderAuthorizationHandler,
)
from mconet.auth.basic.bearer_authorization import BearerAuthorization
from mconet.auth.basic.bearer_authorization_handler import BearerAuthorizationHandler
from mconet.auth.basic.body_signing_guard import reject_unsupported_body_signing
from mconet.auth.basic.dynamic_credential_source import DynamicCredentialSource
from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.auth.basic.no_authorization_handler import NoAuthorizationHandler
from mconet.core.domain import (
    Authorization,
    Bytes,
    Extensions,
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
    BodySigningMode,
    MutableTransportRequest,
    TransportBody,
)

_PLACEHOLDER = "mconet-test-signing-secret-not-secret"
_NON_NONE_MODES = (
    "precomputed_digest",
    "unsigned_payload",
    "buffered_digest",
    "chunked_signature",
)
_STABLE_MESSAGE = "This authorization cannot apply a body-signing mode."


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


def _context(mode: BodySigningMode) -> AuthorizationContext:
    """Build non-sensitive facts for one selected signing mode."""
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
        body_signing_mode=mode,
    )


def _request() -> MutableTransportRequest:
    """Build one open request the guard must not change."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers(),
        query=QueryParameters(),
        body=TransportBody(Bytes(b"{}"), MediaType("application", "json")),
    )


def _assert_unsupported(error: ModelInteractionError, mode: str) -> None:
    """Require one stable signing failure that does not echo the mode."""
    assert error.code == "unsupported_body_signing"
    assert error.message == _STABLE_MESSAGE
    assert str(error.category.id) == "unsupported_feature"
    assert str(error.phase.id) == "authentication"
    assert mode not in error.message


def test_guard_accepts_only_the_none_mode() -> None:
    """Verify every R1 signing mode shares one content-free failure."""
    reject_unsupported_body_signing("none")
    for mode in _NON_NONE_MODES:
        try:
            reject_unsupported_body_signing(mode)
        except ModelInteractionError as error:
            _assert_unsupported(error, mode)
        else:
            raise AssertionError("Expected a non-none signing mode to fail.")


def test_handlers_reject_body_signing_before_reading_a_credential() -> None:
    """Verify each R1 handler fails before its credential source is called."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_PLACEHOLDER)

    source = DynamicCredentialSource(provider)
    cases: tuple[tuple[AuthorizationHandler, Authorization], ...] = (
        (NoAuthorizationHandler(), NoAuthorization()),
        (
            ApiKeyHeaderAuthorizationHandler(),
            ApiKeyHeaderAuthorization("X-Api-Key", "", source),
        ),
        (BearerAuthorizationHandler(), BearerAuthorization(source)),
    )
    for handler, authorization in cases:
        request = _request()
        headers = request.headers

        try:
            asyncio.run(
                handler.apply(authorization, _context("unsigned_payload"), request)
            )
        except ModelInteractionError as error:
            _assert_unsupported(error, "unsigned_payload")
        else:
            raise AssertionError("Expected body signing to fail.")

        assert calls == []
        assert request.headers is headers
        assert request.is_frozen is False
