"""Tests for the testing module boundary."""

import mconet.testing


def test_testing_module_imports_without_public_utilities() -> None:
    """Verify the testing module exports only completed public utilities."""
    assert mconet.testing.__all__ == (
        "SchemaLoader",
        "SchemaValidationIssue",
        "SchemaValidatorAdapter",
        "json_fixtures_equal",
    )
