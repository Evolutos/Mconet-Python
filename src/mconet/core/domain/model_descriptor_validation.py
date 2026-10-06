"""Semantic validation for open model descriptor implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier


def validate_model_descriptor(descriptor: ModelDescriptor) -> ModelDescriptor:
    """Validate a complete open model descriptor without normalizing it.

    Args:
        descriptor: Any structural implementation of ModelDescriptor.

    Returns:
        The same descriptor after successful validation.

    Raises:
        TypeError: If the protocol surface or a field runtime type is invalid.
        ValueError: If name, family, metadata, or extensions violate semantics.
    """
    candidate = cast(object, descriptor)
    # Runtime structural recognition requires every protocol property while
    # preserving the caller's concrete implementation and identity.
    if not isinstance(candidate, ModelDescriptor):
        raise TypeError("descriptor must implement ModelDescriptor.")

    name = cast(object, candidate.name)
    display_name = cast(object, candidate.display_name)
    family = cast(object, candidate.family)
    version = cast(object, candidate.version)
    description = cast(object, candidate.description)

    # A required name must contain at least one non-whitespace character. Its
    # spelling remains opaque and is never parsed into family or version.
    if not isinstance(name, str):
        raise TypeError("ModelDescriptor name must be a string.")
    if not name or name.isspace():
        raise ValueError("ModelDescriptor name must not be empty or whitespace.")

    for field_name, value in (
        ("display_name", display_name),
        ("version", version),
        ("description", description),
    ):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"ModelDescriptor {field_name} must be a string or None.")

    # Family stays open-ended but uses the shared portable identifier grammar.
    if family is not None:
        if not isinstance(family, OpenIdentifier):
            raise TypeError("ModelDescriptor family must be an OpenIdentifier or None.")
        validate_open_identifier(family)

    # Validate metadata and extensions independently so diagnostics identify the
    # correct contract boundary and unknown fields remain uninterpreted.
    _validate_json_mapping(candidate.metadata, "metadata")
    _validate_json_mapping(candidate.extensions, "extensions")
    return candidate


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JsonValue data."""
    if not isinstance(value, Mapping):
        raise TypeError(f"ModelDescriptor {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"ModelDescriptor {field_name} keys must be strings.")

    # Every value is validated independently because Mapping implementations are
    # not required to be concrete dict objects accepted as a whole JsonValue.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
