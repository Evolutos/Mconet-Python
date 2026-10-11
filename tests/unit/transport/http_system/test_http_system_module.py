"""Tests for the transport-http-system module boundary."""

import mconet.transport.http_system
from mconet.transport.http_system import (
    HttpBaseUrl,
    HttpCancellationBridge,
    HttpHeaderField,
    HttpStatusOutcome,
    apply_default_http_headers,
    apply_http_content_length,
    apply_http_content_type,
    ensure_http_deadline,
    extract_http_response_media_type,
    map_http_body,
    map_http_headers,
    map_http_method,
    map_http_query,
    map_http_status,
    map_http_url,
    normalize_http_network_timeout,
    read_bounded_http_response_body,
    summarize_http_response_headers,
)


def test_http_system_transport_exports_request_field_mapping() -> None:
    """Verify the system HTTP module publishes field mapping and defaults."""
    # Connection cancellation and the client remain later work.
    assert mconet.transport.http_system.__all__ == (
        "HttpBaseUrl",
        "HttpCancellationBridge",
        "HttpHeaderField",
        "HttpStatusOutcome",
        "apply_default_http_headers",
        "apply_http_content_length",
        "apply_http_content_type",
        "ensure_http_deadline",
        "extract_http_response_media_type",
        "map_http_body",
        "map_http_headers",
        "map_http_method",
        "map_http_query",
        "map_http_status",
        "map_http_url",
        "normalize_http_network_timeout",
        "read_bounded_http_response_body",
        "summarize_http_response_headers",
    )
    assert mconet.transport.http_system.HttpBaseUrl is HttpBaseUrl
    assert mconet.transport.http_system.HttpCancellationBridge is HttpCancellationBridge
    assert mconet.transport.http_system.HttpHeaderField is HttpHeaderField
    assert mconet.transport.http_system.HttpStatusOutcome is HttpStatusOutcome
    assert (
        mconet.transport.http_system.apply_default_http_headers
        is apply_default_http_headers
    )
    assert mconet.transport.http_system.map_http_body is map_http_body
    assert (
        mconet.transport.http_system.apply_http_content_length
        is apply_http_content_length
    )
    assert (
        mconet.transport.http_system.apply_http_content_type is apply_http_content_type
    )
    assert mconet.transport.http_system.ensure_http_deadline is ensure_http_deadline
    assert (
        mconet.transport.http_system.extract_http_response_media_type
        is extract_http_response_media_type
    )
    assert mconet.transport.http_system.map_http_headers is map_http_headers
    assert mconet.transport.http_system.map_http_method is map_http_method
    assert mconet.transport.http_system.map_http_query is map_http_query
    assert mconet.transport.http_system.map_http_status is map_http_status
    assert mconet.transport.http_system.map_http_url is map_http_url
    assert (
        mconet.transport.http_system.normalize_http_network_timeout
        is normalize_http_network_timeout
    )
    assert (
        mconet.transport.http_system.read_bounded_http_response_body
        is read_bounded_http_response_body
    )
    assert (
        mconet.transport.http_system.summarize_http_response_headers
        is summarize_http_response_headers
    )
