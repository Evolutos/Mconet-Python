"""Tests for the S0 testing module boundary."""

import mconet.testing


def test_testing_module_imports_without_public_utilities() -> None:
    """Verify the empty testing module has no premature utilities."""
    # Test doubles and contract suites belong to S6; S0 creates only the
    # package boundary that will host those reusable testing capabilities.
    assert mconet.testing.__all__ == ()
