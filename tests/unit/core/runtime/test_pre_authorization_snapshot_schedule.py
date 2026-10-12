"""Tests for the pre-authorization snapshot schedule."""

from __future__ import annotations

from mconet.core.domain import (
    Bytes,
    HeaderField,
    Headers,
    MediaType,
    OpenIdentifier,
    QueryParameters,
    UriValue,
)
from mconet.core.runtime._pre_authorization_snapshot_schedule import (
    create_pre_authorization_snapshot,
)
from mconet.core.spi import MutableTransportRequest, TransportBody

_API_KEY = "mconet-test-api-key-not-secret"
_BEARER = "mconet-test-bearer-token-not-secret"


class _Authorization:
    """Authorization decision that names one credential header."""

    def __init__(self) -> None:
        """Store the discriminator and the header that carries the credential."""
        self.kind = OpenIdentifier("authorization.api-key")
        self.header_name = "X-Api-Key"


class _Handler:
    """Handler that snapshot creation must not apply."""

    def __init__(self) -> None:
        """Store an empty call list."""
        self.calls: list[str] = []

    async def apply(self, *values: object) -> None:
        """Record an authorization call."""
        del values
        self.calls.append("apply")


def _request() -> MutableTransportRequest:
    """Return an encoded request that still contains a secret and its body."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/chat/completions", True),
        headers=Headers(
            (
                HeaderField("X-Trace", "trace-value"),
                HeaderField("Authorization", f"Bearer {_BEARER}"),
                HeaderField("X-Api-Key", _API_KEY),
            )
        ),
        query=QueryParameters(),
        body=TransportBody(
            Bytes(_BEARER.encode("utf-8")),
            MediaType("application", "json"),
        ),
    )


def test_snapshot_omits_secret_authorization_header_and_body() -> None:
    """Verify the retained view cannot carry the credential or encoded bytes."""
    request = _request()
    original_body = request.body.bytes
    handler = _Handler()

    snapshot = create_pre_authorization_snapshot(request, _Authorization())

    header_text = " ".join(field.value for field in snapshot.headers.values)
    assert _BEARER not in header_text
    assert _API_KEY not in header_text
    assert _BEARER.encode("utf-8") not in snapshot.body.bytes
    assert snapshot.body.bytes == b""
    assert snapshot.body.media_type == MediaType("application", "json")
    assert snapshot.body is not request.body
    assert request.body.bytes == original_body
    assert handler.calls == []
    assert any(field.name == "X-Trace" for field in snapshot.headers.values)
