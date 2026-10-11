"""Tests for the transport-http-system module boundary."""

import mconet.transport.http_system
from mconet.transport.http_system import (
    HttpBaseUrl,
    HttpCancellationBridge,
    HttpHeaderField,
    HttpProxyEndpoint,
    HttpProxyOverride,
    HttpProxySelection,
    HttpStatusOutcome,
    HttpTlsPolicy,
    apply_default_http_headers,
    apply_http_content_length,
    apply_http_content_type,
    ensure_http_deadline,
    ensure_secure_http_tls,
    extract_http_response_media_type,
    headers_for_http_redirect,
    map_http_body,
    map_http_headers,
    map_http_method,
    map_http_proxy_endpoint,
    map_http_query,
    map_http_status,
    map_http_url,
    normalize_http_network_timeout,
    read_bounded_http_response_body,
    read_bounded_http_response_releasing_connection,
    select_http_proxy,
    summarize_http_response_headers,
    system_http_tls_policy,
)


def test_http_system_transport_exports_request_field_mapping() -> None:
    """Verify the system HTTP module publishes field mapping and defaults."""
    # The transport client remains later work.
    assert mconet.transport.http_system.__all__ == (
        "HttpBaseUrl",
        "HttpCancellationBridge",
        "HttpHeaderField",
        "HttpProxyEndpoint",
        "HttpProxyOverride",
        "HttpProxySelection",
        "HttpStatusOutcome",
        "HttpTlsPolicy",
        "apply_default_http_headers",
        "apply_http_content_length",
        "apply_http_content_type",
        "ensure_http_deadline",
        "ensure_secure_http_tls",
        "extract_http_response_media_type",
        "headers_for_http_redirect",
        "map_http_body",
        "map_http_headers",
        "map_http_method",
        "map_http_proxy_endpoint",
        "map_http_query",
        "map_http_status",
        "map_http_url",
        "normalize_http_network_timeout",
        "read_bounded_http_response_body",
        "read_bounded_http_response_releasing_connection",
        "select_http_proxy",
        "summarize_http_response_headers",
        "system_http_tls_policy",
    )
    assert mconet.transport.http_system.HttpBaseUrl is HttpBaseUrl
    assert mconet.transport.http_system.HttpCancellationBridge is HttpCancellationBridge
    assert mconet.transport.http_system.HttpHeaderField is HttpHeaderField
    assert mconet.transport.http_system.HttpProxyEndpoint is HttpProxyEndpoint
    assert mconet.transport.http_system.HttpProxyOverride is HttpProxyOverride
    assert mconet.transport.http_system.HttpProxySelection is HttpProxySelection
    assert mconet.transport.http_system.HttpStatusOutcome is HttpStatusOutcome
    assert mconet.transport.http_system.HttpTlsPolicy is HttpTlsPolicy
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
    assert mconet.transport.http_system.ensure_secure_http_tls is ensure_secure_http_tls
    assert (
        mconet.transport.http_system.extract_http_response_media_type
        is extract_http_response_media_type
    )
    assert (
        mconet.transport.http_system.headers_for_http_redirect
        is headers_for_http_redirect
    )
    assert mconet.transport.http_system.map_http_headers is map_http_headers
    assert mconet.transport.http_system.map_http_method is map_http_method
    assert (
        mconet.transport.http_system.map_http_proxy_endpoint is map_http_proxy_endpoint
    )
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
        mconet.transport.http_system.read_bounded_http_response_releasing_connection
        is read_bounded_http_response_releasing_connection
    )
    assert mconet.transport.http_system.select_http_proxy is select_http_proxy
    assert (
        mconet.transport.http_system.summarize_http_response_headers
        is summarize_http_response_headers
    )
    assert mconet.transport.http_system.system_http_tls_policy is system_http_tls_policy
