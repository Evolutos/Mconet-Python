"""Tests for the pre-authorization request snapshot."""

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.bearer_authorization import BearerAuthorization
from mconet.auth.basic.dynamic_credential_source import DynamicCredentialSource
from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.core.domain import (
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    QueryParameters,
    SecretValue,
    UriValue,
)
from mconet.core.runtime.pre_authorization_snapshot import (
    snapshot_pre_authorization_request,
)
from mconet.core.spi import (
    AuthorizationContext,
    MutableTransportRequest,
    TransportBody,
)

_API_KEY = "mconet-test-api-key-not-secret"
_BEARER = "mconet-test-bearer-token-not-secret"


def _request() -> MutableTransportRequest:
    """Build one open request that already carries authorization fields."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers(
            (
                HeaderField("X-Trace", "trace-value"),
                HeaderField("Authorization", f"Bearer {_BEARER}"),
                HeaderField("X-Api-Key", _API_KEY),
            )
        ),
        query=QueryParameters(),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def test_api_key_snapshot_drops_authorization_and_the_configured_header() -> None:
    """Verify the key header and Authorization are absent and the key is unread."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_API_KEY)

    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "Key ",
        DynamicCredentialSource(provider),
    )
    request = _request()
    url = request.url
    query = request.query
    body = request.body

    snapshot = snapshot_pre_authorization_request(request, authorization)

    assert snapshot.method == "POST"
    assert snapshot.url is url
    assert snapshot.query is query
    assert snapshot.body is body
    assert snapshot.headers.values == (HeaderField("X-Trace", "trace-value"),)
    assert _API_KEY not in str(snapshot)
    assert _BEARER not in str(snapshot)
    assert calls == []
    assert request.is_frozen is False
    assert not hasattr(snapshot, "authorization")


def test_bearer_snapshot_drops_authorization_without_reading_the_token() -> None:
    """Verify a bearer decision removes Authorization and leaves the token unread."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_BEARER)

    request = MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers(
            (
                HeaderField("X-Trace", "trace-value"),
                HeaderField("authorization", f"Bearer {_BEARER}"),
            )
        ),
        query=QueryParameters(),
        body=TransportBody(Bytes(b"{}"), MediaType("application", "json")),
    )

    snapshot = snapshot_pre_authorization_request(
        request,
        BearerAuthorization(DynamicCredentialSource(provider)),
    )

    assert snapshot.headers.values == (HeaderField("X-Trace", "trace-value"),)
    assert _BEARER not in str(snapshot)
    assert calls == []
    assert request.is_frozen is False


def test_no_authorization_snapshot_still_drops_an_authorization_header() -> None:
    """Verify an explicit no-auth decision does not retain an Authorization field."""
    request = _request()

    snapshot = snapshot_pre_authorization_request(request, NoAuthorization())

    assert snapshot.headers.values == (
        HeaderField("X-Trace", "trace-value"),
        HeaderField("X-Api-Key", _API_KEY),
    )
    assert _BEARER not in str(snapshot)
    assert request.is_frozen is False
