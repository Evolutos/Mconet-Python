"""Tests for the S0 auth-basic module boundary."""

import mconet.auth.basic


def test_basic_auth_imports_without_public_behavior() -> None:
    """Verify the empty basic authorization module has no premature API."""
    # Authorization values and handlers belong to S9; S0 establishes only the
    # independently buildable package boundary for those implementations.
    assert mconet.auth.basic.__all__ == ()
