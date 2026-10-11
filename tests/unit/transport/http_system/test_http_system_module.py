"""Tests for the transport-http-system module boundary."""

import mconet.transport.http_system
from mconet.transport.http_system import map_http_method


def test_http_system_transport_exports_the_method_mapper() -> None:
    """Verify the system HTTP module publishes only method mapping."""
    # Request construction, response reading, and the client remain later work.
    assert mconet.transport.http_system.__all__ == ("map_http_method",)
    assert mconet.transport.http_system.map_http_method is map_http_method
