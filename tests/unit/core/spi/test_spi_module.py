"""Tests for the core-spi module boundary."""

import mconet.core.spi


def test_core_spi_imports_without_public_protocols() -> None:
    """Verify the empty SPI module builds without premature protocols."""
    assert mconet.core.spi.__all__ == ()
