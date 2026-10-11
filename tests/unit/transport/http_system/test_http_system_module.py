"""Tests for the transport-http-system module boundary."""

import mconet.transport.http_system
from mconet.transport.http_system import HttpBaseUrl, map_http_method, map_http_url


def test_http_system_transport_exports_method_and_url_mapping() -> None:
    """Verify the system HTTP module publishes method and URL mapping."""
    # Query mapping, response reading, and the client remain later work.
    assert mconet.transport.http_system.__all__ == (
        "HttpBaseUrl",
        "map_http_method",
        "map_http_url",
    )
    assert mconet.transport.http_system.HttpBaseUrl is HttpBaseUrl
    assert mconet.transport.http_system.map_http_method is map_http_method
    assert mconet.transport.http_system.map_http_url is map_http_url
