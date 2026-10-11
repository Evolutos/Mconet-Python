"""Tests for the transport-http-system module boundary."""

import mconet.transport.http_system
from mconet.transport.http_system import (
    HttpBaseUrl,
    HttpHeaderField,
    apply_default_http_headers,
    map_http_headers,
    map_http_method,
    map_http_query,
    map_http_url,
)


def test_http_system_transport_exports_request_field_mapping() -> None:
    """Verify the system HTTP module publishes field mapping and defaults."""
    # Body writing, response reading, and the client remain later work.
    assert mconet.transport.http_system.__all__ == (
        "HttpBaseUrl",
        "HttpHeaderField",
        "apply_default_http_headers",
        "map_http_headers",
        "map_http_method",
        "map_http_query",
        "map_http_url",
    )
    assert mconet.transport.http_system.HttpBaseUrl is HttpBaseUrl
    assert mconet.transport.http_system.HttpHeaderField is HttpHeaderField
    assert (
        mconet.transport.http_system.apply_default_http_headers
        is apply_default_http_headers
    )
    assert mconet.transport.http_system.map_http_headers is map_http_headers
    assert mconet.transport.http_system.map_http_method is map_http_method
    assert mconet.transport.http_system.map_http_query is map_http_query
    assert mconet.transport.http_system.map_http_url is map_http_url
