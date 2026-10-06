"""Primitive values representable by the language-neutral JSON data model."""

from __future__ import annotations

from typing import TypeAlias

# JSON arrays and objects belong to the recursive JsonValue work package. The
# numeric range and finite-value policy are likewise deferred to S1.26.
JsonPrimitive: TypeAlias = bool | int | float | str | None
"""A JSON null, boolean, number, or string primitive."""
