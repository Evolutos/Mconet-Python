"""Field, ownership, and generated-document tests for ConversationTaskResult."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from typing import Literal, Protocol, cast, runtime_checkable

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationTaskResult,
    Extensions,
    JsonValue,
    MessageDocument,
    MessageElementKind,
    MessageGroup,
    ModelTaskResult,
    OpenIdentifier,
    TaskDescriptor,
    TaskNode,
    validate_task_document,
)


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide a complete MessageElementKind for result message fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined message Kind identity."""

    category: str
    """Open message element classification category."""

    composition: Literal["leaf", "container"]
    """Message tree composition retained for document validation."""


@runtime_checkable
class _MessageCarrier(Protocol):
    """Describe the internal result leaf surface observable through TaskNode."""

    @property
    def messages(self) -> MessageDocument:
        """Return the independent MessageDocument carried by the result leaf."""
        # This test-only structural view inspects public data without importing or
        # exposing the production module's private supporting node type.
        ...


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected storage diagnostic."""
    # Match the field-specific message so an unrelated fixture or assignment
    # failure cannot accidentally satisfy a negative result test.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _messages(
    *,
    version: str = "1.0",
    purpose: Literal["input", "output", "context", "custom"] = "output",
) -> MessageDocument:
    """Create one independently versioned message result document."""
    # An empty concrete root is sufficient to test domain composition while
    # retaining a standard Kind that complete MessageDocument validation accepts.
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    return MessageDocument(
        version,
        purpose,
        MessageGroup("message-root", kind, ()),
    )


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Crossing the static read-only boundary proves the runtime proxy enforces the
    # same membership ownership guarantee as the public Mapping annotation.
    mapping["changed"] = True


def _mutate_descriptor_type(result: ConversationTaskResult) -> None:
    """Attempt to replace the fixed descriptor type through a low-level setter."""
    # The storage-free descriptor has no writable backing field, so even direct
    # object assignment cannot reclassify this or another conversation result.
    object.__setattr__(
        result.descriptor,
        "type",
        OpenIdentifier("vendor.changed"),
    )


def test_conversation_task_result_has_fixed_descriptor_and_protocol_shape() -> None:
    """Verify concrete results implement the open result protocol exactly."""
    messages = _messages()
    result = ConversationTaskResult(messages)
    task_result: ModelTaskResult = result
    descriptor: TaskDescriptor = result.descriptor

    # Structural conformance exposes all independently owned result values, while
    # fixed identity cannot be inferred from or changed by response messages.
    assert isinstance(result, ModelTaskResult)
    assert task_result.document is result.document
    assert task_result.artifacts.artifacts == ()
    assert task_result.metadata == {}
    assert task_result.extensions == {}
    assert descriptor.type == OpenIdentifier("conversation.generate")
    assert descriptor.version is None
    assert descriptor.input_schema_id is None
    assert descriptor.output_schema_id is None
    assert descriptor.metadata == {}
    assert descriptor.extensions == {}

    _assert_raises(
        AttributeError,
        lambda: _mutate_descriptor_type(result),
        "has no setter",
    )
    assert result.descriptor.type == OpenIdentifier("conversation.generate")


def test_conversation_task_result_embeds_messages_once_in_valid_task_tree() -> None:
    """Verify one private result leaf carries the authoritative MessageDocument."""
    messages = _messages(version="2.0")
    result = ConversationTaskResult(messages)
    document = result.document

    # Task schema version is independently fixed and does not copy the Message
    # schema version. The single leaf retains exact MessageDocument identity.
    assert document.version == "1.0"
    assert messages.version == "2.0"
    assert document.root.id == "root"
    assert document.root.kind.id == OpenIdentifier("task.root")
    assert len(document.root.children) == 1
    node: TaskNode = document.root.children[0]
    assert node.id == "result"
    assert node.kind.id == OpenIdentifier("task.result")
    assert node.kind.composition == "leaf"
    assert node.children == ()
    assert node.relations == ()
    assert node.metadata == {}
    assert node.extensions == {}
    assert isinstance(node, _MessageCarrier)
    assert node.messages is messages
    assert result.messages is messages
    assert validate_task_document(document) is document


def test_conversation_task_result_preserves_catalog_and_mapping_ownership() -> None:
    """Verify exact result Catalog identity and isolated mappings remain observable."""
    artifacts = ArtifactCatalog()
    metadata: dict[str, JsonValue] = {"providerRequestId": "request-7"}
    extensions: dict[str, JsonValue] = {"vendor.confidence": 0.92}
    result = ConversationTaskResult(
        _messages(),
        artifacts=artifacts,
        metadata=metadata,
        extensions=extensions,
    )

    # Catalog remains the caller's result-local scope, while both mappings detach
    # top-level membership and reject writes after result construction.
    metadata["providerRequestId"] = "changed"
    extensions["other"] = False
    assert result.artifacts is artifacts
    assert result.metadata == {"providerRequestId": "request-7"}
    assert result.extensions == {"vendor.confidence": 0.92}
    _assert_raises(
        FrozenInstanceError,
        lambda: result.__setattr__("messages", _messages()),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], result.metadata)),
        "does not support item assignment",
    )


def test_conversation_task_result_constructor_exposes_only_owned_inputs() -> None:
    """Verify fixed descriptor and generated document cannot be injected."""
    constructor_fields = tuple(inspect.signature(ConversationTaskResult).parameters)

    # The constructor accepts the authoritative message result and public result
    # preservation values; descriptor, node, and TaskDocument remain deterministic.
    assert constructor_fields == (
        "messages",
        "artifacts",
        "metadata",
        "extensions",
    )
    for field_name in (
        "descriptor",
        "document",
        "result_node",
        "target",
        "resolved_model",
        "status",
        "usage",
        "diagnostics",
        "protocol_state",
    ):
        assert field_name not in constructor_fields


def test_conversation_task_result_definition_defers_nested_semantics() -> None:
    """Verify Message and recursive JSON semantics remain response-validation work."""
    pending_messages = _messages(version="", purpose="input")
    pending_json = cast(JsonValue, ("not", "portable"))
    result = ConversationTaskResult(
        pending_messages,
        metadata={"pending": pending_json},
    )

    # Construction preserves invalid but correctly shaped nested semantics without
    # normalization so later response validation can report their exact domains.
    assert result.messages is pending_messages
    assert result.messages.version == ""
    assert result.messages.purpose == "input"
    assert result.metadata["pending"] is pending_json


def test_conversation_task_result_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass concrete ownership boundaries."""
    messages = _messages()
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ConversationTaskResult(cast(MessageDocument, messages.root)),
            "messages must be a MessageDocument",
        ),
        (
            lambda: ConversationTaskResult(
                messages,
                artifacts=cast(ArtifactCatalog, None),
            ),
            "artifacts must be an ArtifactCatalog",
        ),
        (
            lambda: ConversationTaskResult(
                messages,
                metadata=cast(Extensions, []),
            ),
            "metadata must be a mapping",
        ),
        (
            lambda: ConversationTaskResult(
                messages,
                metadata=cast(Extensions, {1: True}),
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: ConversationTaskResult(
                messages,
                extensions=cast(Extensions, "invalid"),
            ),
            "extensions must be a mapping",
        ),
    )

    # Each scenario changes one storage boundary only; nested semantic validation
    # remains outside this definition work while construction stays type-safe.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
