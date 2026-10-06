"""Serializable descriptive data attached to artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from mconet.core.domain.json_value import JsonValue

# Expose a read-only mapping contract so callers cannot depend on mutation and
# restrict every stored value to the recursive language-neutral JSON data model.
ArtifactMetadata: TypeAlias = Mapping[str, JsonValue]
"""Read-only, string-keyed artifact metadata containing only JSON values."""
