"""Tests for the S0 transport-http-system module boundary."""

import mconet.transport.http_system


def test_http_system_transport_imports_without_public_behavior() -> None:
    """Verify the empty system HTTP module has no premature behavior."""
    # Platform HTTP behavior belongs to S8; S0 establishes only the package
    # boundary that later implements the transport SPI.
    assert mconet.transport.http_system.__all__ == ()
