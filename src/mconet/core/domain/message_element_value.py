"""JSON-only value semantics for generic message elements."""

from __future__ import annotations

from typing import TypeAlias

from mconet.core.domain.json_value import JsonValue

# Keep the element value wire shape identical to JsonValue instead of adding a
# Python-specific wrapper object. Specialized message payloads remain concrete
# element or content fields rather than widening this alias with domain objects.
MessageElementValue: TypeAlias = JsonValue
"""A JSON value carried directly by a generic message element value field."""
