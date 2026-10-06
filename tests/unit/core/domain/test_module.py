"""Tests for the public core-domain module boundary."""

import mconet.core.domain


def test_core_domain_exports_only_completed_public_types() -> None:
    """Verify the domain root exposes only its implemented S1 types."""
    # Each later work package extends this explicit tuple only after its own
    # implementation and tests are complete.
    assert mconet.core.domain.__all__ == (
        "Bytes",
        "Extensions",
        "JsonPrimitive",
        "JsonValue",
        "OpenIdentifier",
        "validate_open_identifier",
    )
