"""Primitive values representable by the language-neutral JSON data model."""

from __future__ import annotations

from typing import TypeAlias

# JsonValue adds arrays and objects; a separate contract defines numeric ranges
# and finite-value requirements.
JsonPrimitive: TypeAlias = bool | int | float | str | None
"""A JSON null, boolean, number, or string primitive."""
