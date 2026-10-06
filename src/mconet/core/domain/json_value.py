"""Recursive values representable by the language-neutral JSON data model."""

from __future__ import annotations

from typing import TypeAlias

from mconet.core.domain.json_primitive import JsonPrimitive

# Concrete list and dict branches match Python's native JSON representation
# without accidentally admitting tuples, bytes, or arbitrary collection types.
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
"""A recursive JSON primitive, array, or string-keyed object."""
