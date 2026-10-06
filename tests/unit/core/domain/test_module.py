"""Tests for the public core-domain module boundary."""

import mconet.core.domain


def test_core_domain_exports_only_completed_public_types() -> None:
    """Verify the domain root exposes only implemented public types."""
    # Keep exports explicit so incomplete types cannot enter the public API.
    assert mconet.core.domain.__all__ == (
        "Bytes",
        "Duration",
        "Extensions",
        "JsonPrimitive",
        "JsonValue",
        "OpenIdentifier",
        "Timestamp",
        "parse_timestamp",
        "validate_duration",
        "validate_open_identifier",
    )
