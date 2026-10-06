"""Semantic validation for open message role implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_role import MessageRole
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier


def validate_message_role(role: MessageRole) -> MessageRole:
    """Validate a complete standard or unknown role without normalizing it.

    Args:
        role: Any structural implementation of MessageRole.

    Returns:
        The same role object after successful validation.

    Raises:
        TypeError: If the protocol surface or a field runtime type is invalid.
        ValueError: If the role identifier or extension data is not portable.

    Notes:
        Validation deliberately does not decide whether a protocol adapter
        supports the role. Known-role policy remains separate from the open
        domain contract so future identifiers can pass through losslessly.
    """
    candidate = cast(object, role)
    # Require the complete structural surface before reading individual fields;
    # optional values may be None, but their properties must still be present.
    if not isinstance(candidate, MessageRole):
        raise TypeError("role must implement MessageRole.")

    identifier = cast(object, candidate.id)
    semantic = cast(object, candidate.semantic)
    raw_value = cast(object, candidate.raw_value)

    # Standard and provider-defined roles share the same portable open-ID rules.
    # No known-value table or fallback role is consulted at this boundary.
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("MessageRole id must be an OpenIdentifier.")
    validate_open_identifier(identifier)

    # Descriptive and original-wire text remain opaque, including empty strings;
    # only the declared optional primitive type is enforced here.
    for field_name, value in (("semantic", semantic), ("raw_value", raw_value)):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"MessageRole {field_name} must be a string or None.")

    _validate_extensions(cast(object, candidate.extensions))
    return candidate


def _validate_extensions(value: object) -> None:
    """Require string-keyed portable JSON role extension data."""
    if not isinstance(value, Mapping):
        raise TypeError("MessageRole extensions must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError("MessageRole extensions keys must be strings.")

    # Mapping implementations need not be concrete dict objects, so validate
    # each preserved value independently through the shared recursive policy.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
