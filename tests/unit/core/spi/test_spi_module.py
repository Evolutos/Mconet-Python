"""Tests for the S0 core-spi module boundary."""

import mconet.core.spi


def test_core_spi_imports_without_public_protocols() -> None:
    """Verify the empty SPI module builds without premature protocols."""
    # S0 establishes only the package boundary; every behavioral protocol is
    # introduced and reviewed by its own later work package.
    assert mconet.core.spi.__all__ == ()
