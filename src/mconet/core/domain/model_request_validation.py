"""Semantic validation for task-neutral model interaction requests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mconet.core.domain.artifact_catalog_validation import validate_artifact_catalog
from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.conversation_task_request_validation import (
    validate_conversation_task_request,
)
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_target_validation import validate_model_target
from mconet.core.domain.model_task_request import ModelTaskRequest
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.domain.service_access_validation import validate_service_access
from mconet.core.domain.task_descriptor_validation import validate_task_descriptor
from mconet.core.domain.task_document_validation import validate_task_document


def validate_model_request(request: ModelRequest) -> ModelRequest:
    """Validate one complete task-neutral request before any model I/O.

    Args:
        request: Any structural implementation of ModelRequest.

    Returns:
        The same request object after all composed domains are valid.

    Raises:
        TypeError: If the request surface or a nested runtime type is invalid.
        ValueError: If target, task, access, or JSON semantics are invalid.
        ModelInteractionError: If a known task is outside its supported execution
            scope.

    Notes:
        Open task implementations receive common domain validation without being
        rejected as unsupported. Separate execution gates own task-type, mode,
        and unknown-node support policy.
    """
    candidate = cast(object, request)
    # Require the complete structural envelope while retaining application-owned
    # implementations and avoiding a concrete request registry or reconstruction.
    if not isinstance(candidate, ModelRequest):
        raise TypeError("request must implement ModelRequest.")

    # Validate routing before task or access so callers receive target-local
    # diagnostics without any fallback resolution, component work, or model I/O.
    validate_model_target(candidate.target)

    # Known task families own additional composition and supported-scope rules;
    # open task families still cross the complete common domain boundary.
    _validate_task(cast(object, candidate.task))

    access = cast(object, candidate.service_access)
    # None explicitly means this request layer supplies no access override. A
    # later resolver, not validation, may consult interaction or client defaults.
    if access is not None:
        validate_service_access(cast(ServiceAccess, access))

    # Request preservation channels remain separate from equivalent task fields
    # and must independently contain portable string-keyed JSON object data.
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_task(value: object) -> None:
    """Validate known task composition or the complete open task boundary."""
    # Structural recognition requires descriptor, document, artifacts, metadata,
    # and extensions even when Core has no task-specific implementation yet.
    if not isinstance(value, ModelTaskRequest):
        raise TypeError("ModelRequest task must implement ModelTaskRequest.")

    if isinstance(value, ConversationTaskRequest):
        # The concrete conversation validator adds input cardinality, parameter,
        # Message, and current Artifact scope rules to common domain validation.
        validate_conversation_task_request(value)
        return

    # An open task remains semantically validatable without claiming executable
    # support: validate every common owned value but preserve its concrete type.
    validate_task_descriptor(value.descriptor)
    validate_task_document(value.document)
    validate_artifact_catalog(value.artifacts)
    _validate_json_mapping(cast(object, value.metadata), "task metadata")
    _validate_json_mapping(cast(object, value.extensions), "task extensions")


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require one string-keyed mapping of portable recursive JSON values."""
    # Accept custom Mapping implementations while excluding sequences, scalars,
    # and non-string keys that cannot represent a language-neutral JSON object.
    if not isinstance(value, Mapping):
        raise TypeError(f"ModelRequest {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"ModelRequest {field_name} keys must be strings.")

    # Preserve unknown keys without interpretation while enforcing the shared
    # recursive shape, cycle, safe-integer, and finite-number boundary.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
