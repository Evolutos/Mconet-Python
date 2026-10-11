"""Tests for the post-authorization monitor request view."""

from typing import cast

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.dynamic_credential_source import DynamicCredentialSource
from mconet.core.domain import (
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    QueryParameters,
    SecretValue,
    UriValue,
)
from mconet.core.runtime.post_authorization_monitor import request_view_for_monitor
from mconet.core.spi import (
    AuthorizationContext,
    MutableTransportRequest,
    TransportBody,
    TransportRequest,
)

_API_KEY = "mconet-test-api-key-not-secret"


def _authorized_request() -> TransportRequest:
    """Build the immutable request authorization would hand to transport."""
    return TransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers(
            (
                HeaderField("X-Trace", "trace-value"),
                HeaderField("Authorization", f"Bearer {_API_KEY}"),
                HeaderField("X-Api-Key", f"Key {_API_KEY}"),
            )
        ),
        query=QueryParameters(),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def test_monitor_view_omits_authorization_headers_without_reading_the_key() -> None:
    """Verify a monitor sees the payload and not the applied credential."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_API_KEY)

    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "Key ",
        DynamicCredentialSource(provider),
    )
    request = _authorized_request()

    view = request_view_for_monitor(request, authorization)

    assert view.method == request.method
    assert view.url is request.url
    assert view.query is request.query
    assert view.body is request.body
    assert view.headers.values == (HeaderField("X-Trace", "trace-value"),)
    assert _API_KEY not in str(view)
    assert calls == []
    assert request.headers.values != view.headers.values


def test_monitor_view_rejects_the_open_request_without_reading_it() -> None:
    """Verify a mutable authorization window is not observable."""
    request = MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers((HeaderField("X-Api-Key", _API_KEY),)),
        query=QueryParameters(),
        body=TransportBody(Bytes(b"{}"), MediaType("application", "json")),
    )
    headers = request.headers

    try:
        request_view_for_monitor(
            cast(TransportRequest, request),
            ApiKeyHeaderAuthorization(
                "X-Api-Key",
                "",
                DynamicCredentialSource(_unused_provider),
            ),
        )
    except TypeError as error:
        assert str(error) == "A monitor cannot read a MutableTransportRequest."
        assert _API_KEY not in str(error)
    else:
        raise AssertionError("Expected the open request to be rejected.")

    assert request.headers is headers
    assert request.is_frozen is False


async def _unused_provider(_context: AuthorizationContext) -> SecretValue:
    """Fail if a rejected monitor view resolves a credential."""
    raise AssertionError("The credential source must not be called.")
