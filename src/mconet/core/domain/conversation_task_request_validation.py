"""Semantic and supported-scope validation for conversation task requests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from mconet.core.domain.artifact_catalog_scope import (
    validate_empty_artifact_catalog_scope,
)
from mconet.core.domain.conversation_input_node import ConversationInputNode
from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.generation_parameters_node import GenerationParametersNode
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_content_scope import (
    validate_text_message_content_scope,
)
from mconet.core.domain.task_descriptor_validation import validate_task_descriptor
from mconet.core.domain.task_document import TaskDocument
from mconet.core.domain.task_document_validation import validate_task_document
from mconet.core.domain.task_node import TaskNode


def validate_conversation_task_request(
    request: ConversationTaskRequest,
) -> ConversationTaskRequest:
    """Validate one conversation request and its supported execution scope.

    Args:
        request: The concrete immutable conversation task request to validate.

    Returns:
        The same request object after every composed domain and scope is valid.

    Raises:
        TypeError: If the request or one of its fields has an invalid runtime
            type.
        ValueError: If descriptor, document, node cardinality, Message purpose,
            nested values, or JSON data violates the conversation contract.
        ModelInteractionError: If Message content or Artifact data is outside the
            supported text-only, artifact-free execution scope.

    Notes:
        Unknown TaskNode implementations remain preserved at this boundary. The
        separate execution support gate owns ``unsupported_task_node`` failures.
    """
    candidate = cast(object, request)
    # Require the concrete request because its fixed descriptor and owned fields
    # define this composition boundary, not merely an attribute-compatible shape.
    if not isinstance(candidate, ConversationTaskRequest):
        raise TypeError("request must be a ConversationTaskRequest.")

    descriptor = validate_task_descriptor(candidate.descriptor)
    # TaskDescriptor validation keeps types open globally; this concrete request
    # adds the exact task identity required for conversation generation.
    if descriptor.type.value != "conversation.generate":
        raise ValueError(
            "ConversationTaskRequest descriptor type must be conversation.generate."
        )

    document = validate_task_document(candidate.document)
    conversation_inputs, parameter_count = _collect_request_nodes(document)
    # One input document is required and unambiguous. Additional conversation
    # turns remain inside that MessageDocument rather than using sibling nodes.
    if len(conversation_inputs) != 1:
        raise ValueError(
            "ConversationTaskRequest document must contain exactly one "
            "ConversationInputNode."
        )
    # Generation controls are optional but represented by one complete value;
    # multiple nodes would create order-dependent override semantics.
    if parameter_count > 1:
        raise ValueError(
            "ConversationTaskRequest document must contain at most one "
            "GenerationParametersNode."
        )

    messages = conversation_inputs[0].messages
    # A conversation input cannot repurpose an otherwise valid output, context,
    # or custom MessageDocument as request input.
    if messages.purpose != "input":
        raise ValueError(
            "ConversationTaskRequest input messages purpose must be input."
        )
    # The scope gate revalidates the document before requiring nominal text
    # content, preserving precise Message failures ahead of support policy.
    validate_text_message_content_scope(messages)

    # Catalog validation and uniqueness precede the current empty-scope policy;
    # no source is resolved, opened, read, uploaded, or transformed here.
    validate_empty_artifact_catalog_scope(candidate.artifacts)
    _validate_json_mapping(cast(object, candidate.metadata), "metadata")
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _collect_request_nodes(
    document: TaskDocument,
) -> tuple[tuple[ConversationInputNode, ...], int]:
    """Collect conversation inputs and count parameter nodes in one task tree."""
    conversation_inputs: list[ConversationInputNode] = []
    parameter_count = 0
    pending: list[TaskNode] = [document.root]

    # TaskDocument validation already owns topology, IDs, relations, and concrete
    # payload validity. This second iterative pass reads only request cardinality
    # and uses stable child snapshots for open structural node implementations.
    while pending:
        node = pending.pop()
        if isinstance(node, ConversationInputNode):
            conversation_inputs.append(node)
        if isinstance(node, GenerationParametersNode):
            parameter_count += 1
        pending.extend(reversed(_snapshot_children(cast(object, node.children))))

    return tuple(conversation_inputs), parameter_count


def _snapshot_children(value: object) -> tuple[TaskNode, ...]:
    """Return a stable tuple from one open TaskNode child sequence."""
    # Strings and byte buffers satisfy Sequence but cannot represent task node
    # membership, so reject them before materializing the traversal snapshot.
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("TaskNode children must be a sequence.")
    snapshot = tuple(cast(Sequence[object], value))
    # Recheck members because an open mutable sequence may change after complete
    # TaskDocument validation and before request-scope traversal observes it.
    if any(not isinstance(child, TaskNode) for child in snapshot):
        raise TypeError("TaskNode children must contain TaskNode values.")
    return cast(tuple[TaskNode, ...], snapshot)


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed request mapping of portable JSON values."""
    # Accept custom Mapping implementations while rejecting arrays, scalars, and
    # non-string keys that cannot form language-neutral JSON object membership.
    if not isinstance(value, Mapping):
        raise TypeError(f"ConversationTaskRequest {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"ConversationTaskRequest {field_name} keys must be strings.")

    # Unknown keys remain uninterpreted, but every value must cross the same
    # recursive shape, cycle, safe-integer, and finite-number boundary.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
