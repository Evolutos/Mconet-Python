"""Tests for the testing module boundary."""

import mconet.testing


def test_testing_module_imports_without_public_utilities() -> None:
    """Verify the empty testing module has no premature utilities."""
    assert mconet.testing.__all__ == ()
