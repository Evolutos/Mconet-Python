"""Tests for the auth-basic module boundary."""

import mconet.auth.basic


def test_basic_auth_imports_without_public_behavior() -> None:
    """Verify the empty basic authorization module has no premature API."""
    assert mconet.auth.basic.__all__ == ()
