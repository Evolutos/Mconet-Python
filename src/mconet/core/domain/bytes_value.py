"""Immutable binary values for payload and transport domain contracts."""

from __future__ import annotations

from typing import NewType

# A nominal type prevents mutable bytearray and memoryview values from entering
# typed domain contracts while retaining Python bytes' zero-copy value semantics.
Bytes = NewType("Bytes", bytes)
"""An immutable byte sequence whose length is measured in octets."""
