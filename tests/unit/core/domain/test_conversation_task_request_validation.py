"""Composition and scope tests for ConversationTaskRequest validation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

import mconet.core.domain.conversation_task_request_validation as request_validation
from mconet.core.domain import (
    Artifact,
    ArtifactCatalog,
    ArtifactDescriptor,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactSource,
    ConversationInputNode,
    ConversationTaskRequest,
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    JsonValue,
    MessageContent,
    MessageContentKind,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelInteractionError,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
    TextMessageContent,
    validate_conversation_task_request,
)


def _empty_extensions() -> Extensions:
    """Create independent mapping storage for structural test fixtures."""
    # Fresh dictionaries prevent dynamic changes in one fixture from affecting
    # another request scenario through shared mutable defaults.
    return {}


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide open task Kind values for request tree fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined task Kind identity."""

    composition: Literal["leaf", "container"]
    """Tree composition used by TaskDocument validation."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide concrete message group Kind values for document fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined message Kind identity."""

    category: str
    """Message-specific element category."""

    composition: Literal["leaf", "container"]
    """Message tree composition used by document validation."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide a complete structural MessageRole for entry fixtures."""

    id: OpenIdentifier
    """Open participant identity."""

    semantic: str | None = None
    """Optional role guidance omitted by default."""

    raw_value: str | None = None
    """Optional external spelling omitted by default."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable role fields."""


@dataclass(frozen=True, slots=True)
class _ContentKind:
    """Provide an open MessageContent Kind identity."""

    id: OpenIdentifier
    """Content representation identity."""


@dataclass(frozen=True, slots=True)
class _UnknownContent:
    """Represent valid non-text content outside the supported request scope."""

    id: str
    """Message-document-local content identity."""

    kind: MessageContentKind
    """Open non-text content Kind."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive content data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable content fields."""


@dataclass(frozen=True, slots=True)
class _CustomTaskNode:
    """Represent an unknown TaskNode retained until its separate support gate."""

    id: str
    """Task-document-local node identity."""

    kind: TaskNodeKind
    """Open custom node classification."""

    children: Sequence[TaskNode] = ()
    """Ordered child sequence empty for this leaf fixture."""

    relations: Sequence[TaskRelation] = ()
    """Ordered directed task relations."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive node data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable node fields."""


@dataclass(frozen=True, slots=True)
class _ArtifactKind:
    """Provide a valid open ArtifactKind for non-empty catalog tests."""

    id: OpenIdentifier
    """Open artifact semantic identity."""

    semantic: str | None = None
    """Optional producer guidance omitted by default."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable Kind fields."""


@dataclass(frozen=True, slots=True)
class _ArtifactSource:
    """Provide a data-only ArtifactSource without I/O behavior."""

    kind: OpenIdentifier
    """Open source representation identity."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    """Provide one valid structural Artifact catalog member."""

    id: str
    """Identity local to the enclosing ArtifactCatalog."""

    kind: ArtifactKind
    """Open artifact semantic classification."""

    media_type: str | None
    """Optional declared media type."""

    source: ArtifactSource
    """Data-only content origin."""

    descriptor: ArtifactDescriptor | None = None
    """Optional modality descriptor omitted by default."""

    metadata: ArtifactMetadata = field(default_factory=_empty_extensions)
    """Portable intrinsic Artifact data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable Artifact fields."""


@dataclass(frozen=True, slots=True)
class _WrongDescriptor:
    """Provide a complete descriptor with a non-conversation task identity."""

    type: OpenIdentifier
    """Portable but incorrect task identity."""

    version: str | None = None
    """Optional descriptor version."""

    input_schema_id: str | None = None
    """Optional input schema identity."""

    output_schema_id: str | None = None
    """Optional output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptor metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable descriptor fields."""


_WRONG_DESCRIPTOR: TaskDescriptor = _WrongDescriptor(OpenIdentifier("embedding.create"))


class _WrongDescriptorRequest(ConversationTaskRequest):
    """Override only the fixed descriptor for concrete validation testing."""

    __slots__ = ()

    @property
    def descriptor(self) -> TaskDescriptor:
        """Return a valid descriptor with the wrong task identity."""
        # The subclass isolates the concrete exact-type rule after generic
        # TaskDescriptor validation has succeeded.
        return _WRONG_DESCRIPTOR


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after matching its diagnostic fragment."""
    # A narrow exception boundary prevents unrelated fixture setup failures from
    # satisfying request composition or support-policy assertions accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _overwrite_field(value: object, field_name: str, replacement: object) -> None:
    """Replace one frozen field to emulate an untyped decoder boundary."""
    # object.__setattr__ deliberately bypasses constructor checks so the public
    # Validator's defensive runtime branches receive otherwise impossible data.
    object.__setattr__(value, field_name, replacement)


def _call_child_snapshot(value: object) -> tuple[TaskNode, ...]:
    """Invoke the package-internal child snapshot through a typed dynamic lookup."""
    # getattr keeps the helper private to production while explicit narrowing
    # gives Pyright a complete callable contract for focused branch testing.
    snapshot = cast(
        Callable[[object], tuple[TaskNode, ...]],
        vars(request_validation)["_snapshot_children"],
    )
    return snapshot(value)


def _message_document(
    *content: MessageContent,
    purpose: Literal["input", "output", "context", "custom"] = "input",
) -> MessageDocument:
    """Create one valid message document with caller-selected content and purpose."""
    # A single standard user entry makes text-scope behavior explicit while the
    # root remains a concrete container accepted by full document validation.
    entry = MessageEntry(
        "entry",
        cast(MessageRole, _Role(OpenIdentifier("message.user"))),
        content or (TextMessageContent("content", "hello"),),
    )
    root_kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    return MessageDocument(
        "1.0",
        purpose,
        MessageGroup("message-root", root_kind, (entry,)),
    )


def _task_document(*children: TaskNode, version: str = "1.0") -> TaskDocument:
    """Create one standard task root containing exact ordered children."""
    # The helper makes cardinality scenarios differ only by their supplied node
    # sequence while retaining one valid root and document version.
    root_kind: TaskNodeKind = _TaskKind(
        OpenIdentifier("task.root"),
        "container",
    )
    return TaskDocument(
        version,
        TaskGroupNode("root", root_kind, children),
    )


def _request(
    *children: TaskNode,
    artifacts: ArtifactCatalog | None = None,
    metadata: Extensions | None = None,
    extensions: Extensions | None = None,
) -> ConversationTaskRequest:
    """Create one conversation request with explicit scope overrides."""
    # None selects a concrete empty Catalog or fresh mappings; callers can still
    # pass an intentionally empty value without it being treated as absent.
    return ConversationTaskRequest(
        _task_document(*children),
        artifacts=artifacts if artifacts is not None else ArtifactCatalog(),
        metadata=metadata if metadata is not None else {},
        extensions=extensions if extensions is not None else {},
    )


def _input(
    node_id: str = "input",
    *,
    messages: MessageDocument | None = None,
) -> ConversationInputNode:
    """Create one conversation input around a selected message document."""
    # A concrete default keeps ordinary request scenarios inside the text-only
    # supported range while allowing exact invalid Message documents when needed.
    return ConversationInputNode(
        node_id,
        messages if messages is not None else _message_document(),
    )


def test_validator_accepts_valid_request_and_preserves_unknown_nodes() -> None:
    """Verify composed valid values retain identity and unknown nodes remain open."""
    input_node = _input()
    parameters = GenerationParametersNode(
        "parameters",
        GenerationParameters(max_output_tokens=128),
    )
    custom = _CustomTaskNode(
        "custom",
        _TaskKind(OpenIdentifier("vendor.future"), "leaf"),
    )
    request = _request(input_node, parameters, custom)

    # The request gate validates known scopes without rebuilding the object or
    # prematurely claiming the separate unknown-node support policy.
    assert validate_conversation_task_request(request) is request
    assert request.document.root.children == (input_node, parameters, custom)
    assert request.artifacts.artifacts == ()


def test_validator_rejects_wrong_request_and_descriptor_types() -> None:
    """Verify nominal request and fixed task identity fail independently."""
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_request(
            cast(ConversationTaskRequest, object())
        ),
        "request must be a ConversationTaskRequest",
    )
    wrong_descriptor = _WrongDescriptorRequest(_task_document(_input()))
    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_request(wrong_descriptor),
        "descriptor type must be conversation.generate",
    )


def test_validator_delegates_complete_task_document_validation() -> None:
    """Verify malformed task documents retain their original diagnostics."""
    request = ConversationTaskRequest(_task_document(_input(), version=""))

    # Descriptor validation succeeds first, then the complete TaskDocument gate
    # reports its own version failure before request cardinality or scope checks.
    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_request(request),
        "TaskDocument version must not be empty",
    )


def test_validator_requires_exactly_one_conversation_input() -> None:
    """Verify missing and ambiguous MessageDocument owners fail structurally."""
    missing = _request(GenerationParametersNode("parameters", GenerationParameters()))
    duplicate = _request(_input("input-1"), _input("input-2"))

    # Conversation history belongs inside one MessageDocument; sibling input
    # nodes cannot create an implicit ordering or merge rule.
    for request in (missing, duplicate):
        _assert_raises(
            ValueError,
            lambda request=request: validate_conversation_task_request(request),
            "must contain exactly one ConversationInputNode",
        )


def test_validator_allows_at_most_one_generation_parameter_node() -> None:
    """Verify optional controls cannot create order-dependent overrides."""
    request = _request(
        _input(),
        GenerationParametersNode("parameters-1", GenerationParameters()),
        GenerationParametersNode("parameters-2", GenerationParameters()),
    )

    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_request(request),
        "must contain at most one GenerationParametersNode",
    )


def test_validator_requires_input_message_purpose() -> None:
    """Verify valid non-input Message documents cannot act as request input."""
    request = _request(_input(messages=_message_document(purpose="output")))

    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_request(request),
        "input messages purpose must be input",
    )


def test_validator_delegates_text_message_scope() -> None:
    """Verify valid open non-text content fails with the stable scope error."""
    unknown = _UnknownContent(
        "rich-content",
        _ContentKind(OpenIdentifier("vendor.rich_text")),
    )
    request = _request(_input(messages=_message_document(unknown)))

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_conversation_task_request(request),
            "Only TextMessageContent is supported",
        ),
    )
    # Preserve the existing normalized support contract rather than translating
    # it into a request-specific exception or leaking the content identity.
    assert error.code == "unsupported_message_content"
    assert "rich-content" not in str(error)


def test_validator_delegates_generation_parameter_validation() -> None:
    """Verify invalid controls fail during TaskDocument payload validation."""
    request = _request(
        _input(),
        GenerationParametersNode(
            "parameters",
            GenerationParameters(max_output_tokens=0),
        ),
    )

    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_request(request),
        "max_output_tokens must be positive",
    )


def test_validator_delegates_empty_artifact_scope() -> None:
    """Verify a valid non-empty Catalog fails after composed domain validation."""
    artifact: Artifact = _Artifact(
        "artifact-1",
        _ArtifactKind(OpenIdentifier("artifact.file")),
        "application/octet-stream",
        _ArtifactSource(OpenIdentifier("vendor.memory")),
    )
    request = _request(
        _input(),
        artifacts=ArtifactCatalog((artifact,)),
    )

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_conversation_task_request(request),
            "Only an empty ArtifactCatalog is supported",
        ),
    )
    # Artifact details remain absent from the normalized support failure, and no
    # source behavior exists for the gate to invoke.
    assert error.code == "unsupported_message_content"
    assert "artifact-1" not in str(error)


def test_validator_checks_request_json_channels_independently() -> None:
    """Verify metadata and extensions retain portable recursive JSON rules."""
    malformed: tuple[tuple[ConversationTaskRequest, type[BaseException], str], ...] = (
        (
            _request(_input(), metadata={"invalid": cast(JsonValue, ("tuple",))}),
            TypeError,
            "JsonValue",
        ),
        (
            _request(_input(), extensions={"notFinite": float("inf")}),
            ValueError,
            "must be finite",
        ),
    )

    # Scope and nested domains succeed first, isolating each request-level JSON
    # channel as the only failing boundary in its scenario.
    for request, exception_type, message in malformed:
        _assert_raises(
            exception_type,
            lambda request=request: validate_conversation_task_request(request),
            message,
        )


def test_validator_rechecks_request_mapping_storage() -> None:
    """Verify dynamically corrupted mapping containers and keys fail stably."""
    invalid_metadata = _request(_input())
    invalid_extensions = _request(_input())
    _overwrite_field(invalid_metadata, "metadata", [])
    _overwrite_field(invalid_extensions, "extensions", {1: True})

    # Nested domains and supported scopes succeed before each request-level field
    # is rechecked, isolating the precise dynamic storage diagnostic.
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_request(invalid_metadata),
        "metadata must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_request(invalid_extensions),
        "extensions keys must be strings",
    )


def test_scope_child_snapshot_rejects_invalid_dynamic_sequences() -> None:
    """Verify the second request traversal rejects changed child storage."""
    invalid_values: tuple[tuple[object, str], ...] = (
        (object(), "children must be a sequence"),
        ("node-id", "children must be a sequence"),
        ((object(),), "children must contain TaskNode values"),
    )

    # Direct helper coverage models an open node changing its property after the
    # complete TaskDocument pass, without coupling the test to getter call counts
    # performed by runtime-checkable Protocol recognition.
    for value, message in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: _call_child_snapshot(value),
            message,
        )
