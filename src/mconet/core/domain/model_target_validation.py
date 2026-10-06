"""Semantic validation for open model target implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.model_descriptor_validation import validate_model_descriptor
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier


def validate_model_target(target: ModelTarget) -> ModelTarget:
    """Validate a complete target before any access or transport work.

    Args:
        target: Any structural implementation of ModelTarget.

    Returns:
        The same target after successful validation.

    Raises:
        TypeError: If the protocol surface or a field runtime type is invalid.
        ValueError: If an identifier, model, or extension value is invalid.
    """
    candidate = cast(object, target)
    # Structural recognition requires every target dimension without replacing
    # the caller's concrete implementation or introducing a target registry.
    if not isinstance(candidate, ModelTarget):
        raise TypeError("target must implement ModelTarget.")

    service_id = cast(object, candidate.service_id)
    protocol_id = cast(object, candidate.protocol_id)
    model = cast(object, candidate.model)
    deployment_id = cast(object, candidate.deployment_id)

    # Service and protocol remain independent open identifiers and therefore
    # receive identical nominal and portable-syntax validation.
    for field_name, identifier in (
        ("service_id", service_id),
        ("protocol_id", protocol_id),
    ):
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError(f"ModelTarget {field_name} must be an OpenIdentifier.")
        validate_open_identifier(identifier)

    # A model is mandatory even though runtime structural checks only prove the
    # attribute exists. Delegate its complete semantics to the shared validator.
    if not isinstance(model, ModelDescriptor):
        raise TypeError("ModelTarget model must implement ModelDescriptor.")
    validate_model_descriptor(model)

    # Deployment identifiers are provider-owned opaque text. Empty-string policy
    # is not inferred here because no cross-provider semantic rule defines it.
    if deployment_id is not None and not isinstance(deployment_id, str):
        raise TypeError("ModelTarget deployment_id must be a string or None.")

    _validate_extensions(candidate.extensions)
    return candidate


def _validate_extensions(value: object) -> None:
    """Require string-keyed portable JSON extension data."""
    if not isinstance(value, Mapping):
        raise TypeError("ModelTarget extensions must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError("ModelTarget extensions keys must be strings.")

    # Unknown target fields are preserved without interpretation, but they must
    # remain valid cross-language JSON before the target can reach I/O.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
