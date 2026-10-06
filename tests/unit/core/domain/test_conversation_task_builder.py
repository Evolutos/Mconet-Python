"""Tests for fluent construction of immutable conversation task requests."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationInputNode,
    ConversationTaskBuilder,
    ConversationTaskRequest,
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    JsonValue,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TextMessageContent,
    validate_conversation_task_request,
)


def _empty_extensions() -> Extensions:
    """Create independently owned extension storage for test fixtures."""
    # Fresh dictionaries ensure roles and helper values never share mutable test
    # state while satisfying their public read-only mapping annotations.
    return {}


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide complete open task Kind values for request fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined task node identity."""

    composition: Literal["leaf", "container"]
    """Tree composition used by task document validation."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide complete open message Kind values for request fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined message element identity."""

    category: str
    """Open message element classification category."""

    composition: Literal["leaf", "container"]
    """Tree composition used by message document validation."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide one structurally complete message role for input fixtures."""

    id: OpenIdentifier
    """Open participant role identity."""

    semantic: str | None = None
    """Optional role guidance omitted by ordinary fixtures."""

    raw_value: str | None = None
    """Optional provider spelling omitted by ordinary fixtures."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable role fields retained without interpretation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after matching its diagnostic fragment."""
    # Keep the exception boundary narrow so fixture setup or an unrelated failure
    # cannot accidentally satisfy a negative builder scenario.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _messages(text: str = "Hello 世界 👋") -> MessageDocument:
    """Create one valid text-only conversation input document."""
    # A concrete user entry and standard root exercise the complete nested
    # validation path while keeping each builder scenario focused on task fields.
    role: MessageRole = _Role(OpenIdentifier("message.user"))
    entry = MessageEntry(
        "message-entry",
        role,
        (TextMessageContent("text-content", text),),
    )
    kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    return MessageDocument(
        "1.0",
        "input",
        MessageGroup("message-root", kind, (entry,)),
    )


def _document(
    *,
    messages: MessageDocument | None = None,
) -> TaskDocument:
    """Create a valid task tree with generation controls."""
    # Children are assembled in the direct order expected by protocol adapters;
    # the builder must retain this document and its nested objects unchanged.
    input_node = ConversationInputNode(
        "input",
        messages if messages is not None else _messages(),
    )
    children = (
        input_node,
        GenerationParametersNode(
            "parameters",
            GenerationParameters(
                temperature=0.7,
                top_p=0.9,
                max_output_tokens=256,
                stop=("done",),
                seed=42,
            ),
        ),
    )
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    return TaskDocument("1.0", TaskGroupNode("root", kind, children))


def _empty_task_document() -> TaskDocument:
    """Create a valid task document shape with no conversation input node."""
    # The generic TaskDocument is valid, but the conversation request validator
    # must reject it because task-specific input cardinality is unsatisfied.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    return TaskDocument("1.0", TaskGroupNode("root", kind, ()))


def test_builder_matches_direct_conversation_request_construction() -> None:
    """Verify every builder field equals direct immutable construction."""
    document = _document()
    artifacts = ArtifactCatalog()
    metadata: Extensions = {"locale": "zh-CN", "turn": 2}
    extensions: Extensions = {"vendor.trace": {"enabled": True}}

    builder = ConversationTaskBuilder(document)
    returned = (
        builder.with_artifacts(artifacts)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )
    built = builder.build()
    direct = ConversationTaskRequest(
        document,
        artifacts=artifacts,
        metadata=metadata,
        extensions=extensions,
    )
    validated_direct = validate_conversation_task_request(direct)

    # Fluent calls retain one builder. Dataclass equality proves all task-level
    # fields match direct construction, while identity checks prove no immutable
    # TaskDocument, nested node, or ArtifactCatalog was rebuilt or reordered.
    assert returned is builder
    assert built == validated_direct
    assert built is not validated_direct
    assert built.document is document
    assert built.document.root is document.root
    assert built.artifacts is artifacts
    assert built.document.root.children == document.root.children


def test_builder_owns_channels_and_returns_fresh_request_snapshots() -> None:
    """Verify caller and later builder changes cannot alter built requests."""
    document = _document()
    first_artifacts = ArtifactCatalog()
    second_artifacts = ArtifactCatalog()
    metadata: dict[str, JsonValue] = {"turn": 1}
    extensions: dict[str, JsonValue] = {"vendor.mode": "initial"}
    builder = (
        ConversationTaskBuilder(document)
        .with_artifacts(first_artifacts)
        .with_metadata(metadata)
        .with_extensions(extensions)
    )

    # Fluent mapping calls capture membership immediately, preventing source
    # changes before build from leaking into the builder's construction state.
    metadata["turn"] = 99
    extensions["vendor.extra"] = True
    first = builder.build()

    # Replacing all optional channels affects only later results. Each build
    # creates a distinct frozen request while retaining the same required document.
    builder.with_artifacts(second_artifacts).with_metadata({"turn": 2})
    builder.with_extensions({"vendor.mode": "later"})
    second = builder.build()
    assert first is not second
    assert first.document is document
    assert second.document is document
    assert first.artifacts is first_artifacts
    assert second.artifacts is second_artifacts
    assert first.metadata == {"turn": 1}
    assert first.extensions == {"vendor.mode": "initial"}
    assert second.metadata == {"turn": 2}
    assert second.extensions == {"vendor.mode": "later"}


def test_builders_do_not_share_default_state() -> None:
    """Verify independent builders own distinct default request channels."""
    first_builder = ConversationTaskBuilder(_document())
    second_builder = ConversationTaskBuilder(_document(messages=_messages("second")))
    first_builder.with_metadata({"owner": "first"}).with_extensions(
        {"vendor.owner": "first"}
    )

    # Mutating one builder's channels cannot affect another construction flow;
    # default catalogs are also independently created request-local scopes.
    first = first_builder.build()
    second = second_builder.build()
    assert first.metadata == {"owner": "first"}
    assert first.extensions == {"vendor.owner": "first"}
    assert second.metadata == {}
    assert second.extensions == {}
    assert first.artifacts is not second.artifacts
    assert first.artifacts.artifacts == second.artifacts.artifacts == ()


def test_builder_delegates_complete_request_semantics() -> None:
    """Verify build reuses conversation request validation without rule copies."""
    invalid_cases: tuple[
        tuple[ConversationTaskBuilder, type[BaseException], str], ...
    ] = (
        (
            ConversationTaskBuilder(_empty_task_document()),
            ValueError,
            "exactly one ConversationInputNode",
        ),
        (
            ConversationTaskBuilder(_document()).with_metadata(
                {"invalid": cast(JsonValue, ("tuple",))}
            ),
            TypeError,
            "JsonValue",
        ),
    )

    # Diagnostics originate from the existing composed Validator at build time,
    # demonstrating that the Builder has no divergent document or JSON rules.
    for builder, exception_type, message in invalid_cases:
        _assert_raises(exception_type, builder.build, message)


def test_builder_rejects_invalid_storage_without_partial_mutation() -> None:
    """Verify fluent storage checks run before replacing valid builder state."""
    document = _document()
    artifacts = ArtifactCatalog()
    builder = ConversationTaskBuilder(document).with_artifacts(artifacts)
    invalid_actions: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ConversationTaskBuilder(cast(TaskDocument, object())),
            "document must be a TaskDocument",
        ),
        (
            lambda: builder.with_artifacts(cast(ArtifactCatalog, object())),
            "artifacts must be an ArtifactCatalog",
        ),
        (
            lambda: builder.with_metadata(cast(Extensions, [])),
            "metadata must be a mapping",
        ),
        (
            lambda: builder.with_extensions(cast(Extensions, {1: True})),
            "extensions keys must be strings",
        ),
    )

    # Every invalid operation fails before mutation. The same builder remains
    # usable and produces a request containing only its prior valid state.
    for action, message in invalid_actions:
        _assert_raises(TypeError, action, message)
    built = builder.build()
    assert built.document is document
    assert built.artifacts is artifacts
    assert built.metadata == {}
    assert built.extensions == {}


def test_builder_surface_contains_only_task_request_fields() -> None:
    """Verify the builder does not absorb model, access, protocol, or I/O data."""
    constructor_parameters = tuple(
        inspect.signature(ConversationTaskBuilder).parameters
    )
    public_methods = {
        name
        for name, _ in inspect.getmembers(
            ConversationTaskBuilder,
            inspect.isfunction,
        )
        if not name.startswith("_")
    }

    # The required field and fluent methods map one-to-one to the concrete task
    # request constructor plus validation, leaving outer request concerns absent.
    assert constructor_parameters == ("document",)
    assert public_methods == {
        "build",
        "with_artifacts",
        "with_extensions",
        "with_metadata",
    }
    for unrelated_name in (
        "target",
        "service_access",
        "authorization",
        "interaction_mode",
        "adapter",
        "transport",
    ):
        assert unrelated_name not in constructor_parameters
        assert unrelated_name not in public_methods
