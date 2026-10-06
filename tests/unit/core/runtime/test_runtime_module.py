"""Tests for the core-runtime module boundary."""

import mconet.core.runtime


def test_core_runtime_imports_without_public_behavior() -> None:
    """Verify the empty runtime module builds without premature behavior."""
    assert mconet.core.runtime.__all__ == ()
