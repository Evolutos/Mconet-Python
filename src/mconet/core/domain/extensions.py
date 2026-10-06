"""Forward-compatible extension values for public domain contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from mconet.core.domain.json_value import JsonValue

# Expose only the read-only mapping protocol so public contracts cannot rely on
# mutation methods; concrete value constructors own any defensive copying.
Extensions: TypeAlias = Mapping[str, JsonValue]
"""A read-only string-keyed mapping of recursive JSON values."""
