"""Tests that credential headers stay out of the response summary."""

from mconet.transport.http_system import (
    HttpHeaderField,
    summarize_http_response_headers,
)

_SECRET = "summary-secret-value"


def test_summarize_http_response_headers_omits_credential_fields() -> None:
    """Verify authorization and cookie fields are absent, not redacted in place."""
    summary = summarize_http_response_headers(
        (
            HttpHeaderField("Content-Type", "application/json"),
            HttpHeaderField("Authorization", f"Bearer {_SECRET}"),
            HttpHeaderField("X-Request-Id", "one"),
            HttpHeaderField("Set-Cookie", f"session={_SECRET}"),
            HttpHeaderField("x-request-id", "two"),
            HttpHeaderField("Cookie", f"a={_SECRET}"),
            HttpHeaderField("Proxy-Authorization", f"Basic {_SECRET}"),
        )
    )

    assert summary == (
        HttpHeaderField("Content-Type", "application/json"),
        HttpHeaderField("X-Request-Id", "one"),
        HttpHeaderField("x-request-id", "two"),
    )
    rendered = " ".join(f"{field.name}:{field.value}" for field in summary)
    assert _SECRET not in rendered
    assert "authorization" not in rendered.casefold()
    assert "cookie" not in rendered.casefold()


def test_summarize_http_response_headers_keeps_an_empty_safe_list() -> None:
    """Verify no credential field is invented for an empty response."""
    assert summarize_http_response_headers(()) == ()
