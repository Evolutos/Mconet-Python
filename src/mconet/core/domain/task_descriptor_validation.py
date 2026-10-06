"""Semantic validation for open task descriptor implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.task_descriptor import TaskDescriptor


def validate_task_descriptor(descriptor: TaskDescriptor) -> TaskDescriptor:
    """Validate a complete open task descriptor without normalizing it.

    Args:
        descriptor: Any structural implementation of TaskDescriptor.

    Returns:
        The same descriptor object after successful validation.

    Raises:
        TypeError: If the protocol surface or a field runtime type is invalid.
        ValueError: If task type, version, metadata, or extensions violate the
            portable task descriptor contract.
    """
    candidate = cast(object, descriptor)
    # Runtime structural recognition requires every public property while
    # preserving application-owned implementations and unknown task types.
    if not isinstance(candidate, TaskDescriptor):
        raise TypeError("descriptor must implement TaskDescriptor.")

    task_type = cast(object, candidate.type)
    version = cast(object, candidate.version)
    input_schema_id = cast(object, candidate.input_schema_id)
    output_schema_id = cast(object, candidate.output_schema_id)

    # Task type is the single required semantic identity. Validate the shared
    # open grammar without comparing against a closed standard-task registry.
    if not isinstance(task_type, OpenIdentifier):
        raise TypeError("TaskDescriptor type must be an OpenIdentifier.")
    validate_open_identifier(task_type)

    # Version remains forward-compatible opaque text. When supplied, it must
    # contain visible content but is not coerced into SchemaVersion or SemVer.
    if version is not None:
        if not isinstance(version, str):
            raise TypeError("TaskDescriptor version must be a string or None.")
        if not version or version.isspace():
            raise ValueError("TaskDescriptor version must not be empty or whitespace.")

    # Input and output schema identities are separate optional opaque strings.
    # Their registry, resolution, and compatibility belong to later consumers.
    for field_name, value in (
        ("input_schema_id", input_schema_id),
        ("output_schema_id", output_schema_id),
    ):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"TaskDescriptor {field_name} must be a string or None.")

    # Validate both JSON channels independently so failures identify the exact
    # boundary and provider-owned keys remain otherwise uninterpreted.
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable JsonValue data."""
    # Accept the Mapping abstraction for custom descriptors, while excluding
    # arrays, scalars, and non-string keys from JSON object channels.
    if not isinstance(value, Mapping):
        raise TypeError(f"TaskDescriptor {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"TaskDescriptor {field_name} keys must be strings.")

    # Validate values independently because arbitrary Mapping implementations
    # are not themselves concrete dict JsonValue containers.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
