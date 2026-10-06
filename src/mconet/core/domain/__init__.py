"""Task-neutral domain contracts and immutable values for Mconet."""

from mconet.core.domain.json_primitive import JsonPrimitive
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier

__all__ = ("JsonPrimitive", "OpenIdentifier", "validate_open_identifier")
