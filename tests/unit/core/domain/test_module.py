"""Tests for the S0 core-domain module boundary."""

import mconet.core.domain


def test_core_domain_imports_without_public_types() -> None:
    """Verify the empty domain module builds and exposes no premature API."""
    # S0 establishes only the package boundary; domain types are introduced by
    # their own later work packages and must not be anticipated here.
    assert mconet.core.domain.__all__ == ()
