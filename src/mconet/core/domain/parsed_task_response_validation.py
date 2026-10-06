"""Semantic validation for parsed model service response facts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast, runtime_checkable

from mconet.core.domain.artifact_catalog_validation import validate_artifact_catalog
from mconet.core.domain.conversation_task_result import ConversationTaskResult
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_document_validation import validate_message_document
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.model_descriptor_validation import validate_model_descriptor
from mconet.core.domain.model_task_result import ModelTaskResult
from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)
from mconet.core.domain.output_status import OutputStatus
from mconet.core.domain.parsed_task_response import ParsedTaskResponse
from mconet.core.domain.protocol_state import ProtocolState
from mconet.core.domain.task_descriptor_validation import validate_task_descriptor
from mconet.core.domain.task_document_validation import validate_task_document
from mconet.core.domain.task_node import TaskNode
from mconet.core.domain.token_usage import TokenUsage


@runtime_checkable
class _MessageResultNode(Protocol):
    """Describe the conversation result leaf's message-bearing surface."""

    @property
    def messages(self) -> MessageDocument:
        """Return the independent output MessageDocument carried by the leaf."""
        # This private structural view verifies the public result composition
        # without exporting or depending on its private concrete node class.
        ...


def validate_parsed_task_response(
    response: ParsedTaskResponse,
) -> ParsedTaskResponse:
    """Validate complete protocol facts without filling absent response fields.

    Args:
        response: The immutable parsed response value to validate.

    Returns:
        The same response object after every present protocol fact is valid.

    Raises:
        TypeError: If the response, a nested contract, or field storage has an
            invalid runtime type.
        ValueError: If task, model, status, usage, state, Message, or JSON
            semantics violate their portable domain contracts.

    Notes:
        ``None`` for resolved model, stop reason, or usage remains authoritative
        absence. Validation never consults a request, derives values from the
        result, or replaces missing service facts with defaults.
    """
    candidate = cast(object, response)
    # Require the concrete parsed value because this boundary owns its complete
    # immutable field set rather than accepting an alternate response protocol.
    if not isinstance(candidate, ParsedTaskResponse):
        raise TypeError("response must be a ParsedTaskResponse.")

    _validate_result(cast(object, candidate.result))

    resolved_model = cast(object, candidate.resolved_model)
    # Absence remains None. A present custom descriptor crosses its existing open
    # semantic validator without reconstruction or model-name normalization.
    if resolved_model is not None:
        if not isinstance(resolved_model, ModelDescriptor):
            raise TypeError(
                "ParsedTaskResponse resolved_model must implement "
                "ModelDescriptor or be None."
            )
        validate_model_descriptor(resolved_model)

    _validate_status(cast(object, candidate.status))

    stop_reason = cast(object, candidate.stop_reason)
    # Stop reasons are provider-owned opaque strings; empty text is preserved and
    # no value is derived from status when the service omitted this field.
    if stop_reason is not None and not isinstance(stop_reason, str):
        raise TypeError("ParsedTaskResponse stop_reason must be a string or None.")

    usage = cast(object, candidate.usage)
    # Token accounting is optional as a whole. Present values are revalidated at
    # this trust boundary without calculating missing counts or totals.
    if usage is not None:
        _validate_usage(usage)

    _validate_protocol_state(cast(object, candidate.protocol_state))
    _validate_json_mapping(cast(object, candidate.extensions), "extensions")
    return candidate


def _validate_result(value: object) -> None:
    """Validate every common result field and known conversation composition."""
    # Structural recognition keeps future task-result implementations open while
    # requiring all five common owned fields before any attribute is consumed.
    if not isinstance(value, ModelTaskResult):
        raise TypeError("ParsedTaskResponse result must implement ModelTaskResult.")
    result = value

    validate_task_descriptor(result.descriptor)
    validate_task_document(result.document)
    validate_artifact_catalog(result.artifacts)
    _validate_json_mapping(cast(object, result.metadata), "result metadata")
    _validate_json_mapping(cast(object, result.extensions), "result extensions")

    # The known concrete result has additional composition semantics; unknown
    # result families remain valid through only their complete common boundary.
    if isinstance(result, ConversationTaskResult):
        _validate_conversation_result(result)


def _validate_conversation_result(result: ConversationTaskResult) -> None:
    """Validate the message result and its single canonical task-tree binding."""
    # A concrete conversation result cannot be reclassified by an overridden or
    # corrupted descriptor even when the alternate descriptor is otherwise valid.
    if result.descriptor.type.value != "conversation.generate":
        raise ValueError(
            "ConversationTaskResult descriptor type must be conversation.generate."
        )

    messages = validate_message_document(result.messages)
    # Conversation output must not repurpose a valid request, context, or custom
    # document; missing output data is represented by an empty output tree.
    if messages.purpose != "output":
        raise ValueError("ConversationTaskResult messages purpose must be output.")

    document = result.document
    root = document.root
    # Constructor-generated IDs make the message-bearing leaf deterministic and
    # prevent another valid task tree from becoming detached from result.messages.
    if root.id != "root":
        raise ValueError("ConversationTaskResult document root id must be root.")
    children = root.children
    if len(children) != 1:
        raise ValueError(
            "ConversationTaskResult document must contain exactly one result node."
        )

    node: TaskNode = children[0]
    if node.id != "result" or node.kind.id.value != "task.result":
        raise ValueError(
            "ConversationTaskResult document child must be the task.result node."
        )
    if not isinstance(node, _MessageResultNode):
        raise TypeError(
            "ConversationTaskResult result node must carry a MessageDocument."
        )
    if node.messages is not messages:
        raise ValueError(
            "ConversationTaskResult result node must carry the result messages."
        )


def _validate_status(value: object) -> None:
    """Require a present OutputStatus with one valid open identifier."""
    # A missing status is invalid rather than being rewritten to completed,
    # failed, or unknown from result content or transport outcome.
    if not isinstance(value, OutputStatus):
        raise TypeError("ParsedTaskResponse status must be an OutputStatus.")
    identifier = cast(object, value.id)
    if not isinstance(identifier, OpenIdentifier):
        raise TypeError("ParsedTaskResponse status id must be an OpenIdentifier.")
    validate_open_identifier(identifier)


def _validate_usage(value: object) -> None:
    """Validate present provider token accounting without inferring counts."""
    if not isinstance(value, TokenUsage):
        raise TypeError("ParsedTaskResponse usage must be a TokenUsage or None.")

    # Each count is independent: None remains absent, zero remains explicit, and
    # total is checked as reported rather than recomputed from input and output.
    for field_name, count in (
        ("input_tokens", cast(object, value.input_tokens)),
        ("output_tokens", cast(object, value.output_tokens)),
        ("total_tokens", cast(object, value.total_tokens)),
    ):
        if count is None:
            continue
        if type(count) is not int:
            raise TypeError(
                f"ParsedTaskResponse usage {field_name} must be an integer or None."
            )
        if count < 0:
            raise ValueError(
                f"ParsedTaskResponse usage {field_name} must not be negative."
            )
        validate_json_value_numbers(cast(JsonValue, count))

    _validate_json_mapping(cast(object, value.extensions), "usage extensions")


def _validate_protocol_state(value: object) -> None:
    """Validate the ordered immutable protocol-state collection and its members."""
    # Tuple storage ensures the response cannot gain or lose state entries between
    # validation and Runtime assembly; absence is the concrete empty tuple.
    if not isinstance(value, tuple):
        raise TypeError("ParsedTaskResponse protocol_state must be a tuple.")

    for state in cast(tuple[object, ...], value):
        if not isinstance(state, ProtocolState):
            raise TypeError(
                "ParsedTaskResponse protocol_state values must be ProtocolState."
            )
        # Keep the three open identity dimensions separate and validate each one
        # before accepting the opaque but portable state payload.
        for field_name, identifier in (
            ("service_id", cast(object, state.service_id)),
            ("protocol_id", cast(object, state.protocol_id)),
            ("state_type", cast(object, state.state_type)),
        ):
            if not isinstance(identifier, OpenIdentifier):
                raise TypeError(
                    "ParsedTaskResponse protocol_state "
                    f"{field_name} must be an OpenIdentifier."
                )
            validate_open_identifier(identifier)
        validate_json_value_numbers(state.state_value)


def _validate_json_mapping(value: object, field_name: str) -> None:
    """Require a string-keyed mapping containing portable recursive JSON values."""
    # Mapping admits immutable proxies and integration-owned implementations while
    # rejecting arrays, scalars, and non-string JSON object member names.
    if not isinstance(value, Mapping):
        raise TypeError(f"ParsedTaskResponse {field_name} must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError(f"ParsedTaskResponse {field_name} keys must be strings.")

    # Values remain uninterpreted, but recursive shape, cycles, safe integers, and
    # finite floating-point semantics must be portable before Runtime assembly.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))
