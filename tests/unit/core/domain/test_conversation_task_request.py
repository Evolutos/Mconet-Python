"""Field, ownership, and descriptor tests for ConversationTaskRequest."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationTaskRequest,
    Extensions,
    JsonValue,
    ModelTaskRequest,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide a complete TaskNodeKind for root document fixtures."""

    id: OpenIdentifier
    """Standard or provider-defined task Kind identity."""

    composition: Literal["leaf", "container"]
    """Task tree composition retained for later validation."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected storage diagnostic."""
    # Match the domain message so an unrelated fixture or assignment failure
    # cannot satisfy a negative request test accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _document(
    *,
    version: str = "1.0",
    root_kind: str = "task.root",
) -> TaskDocument:
    """Create one task document with controllable deferred semantics."""
    # The concrete root keeps request tests independent from custom TaskNode
    # implementations while allowing invalid version and Kind values to persist.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier(root_kind), "container")
    return TaskDocument(version, TaskGroupNode("root", kind, ()))


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt item assignment through a deliberately narrowed mapping type."""
    # Crossing the static read-only boundary proves MappingProxyType enforces the
    # same ownership guarantee at runtime.
    mapping["changed"] = True


def _mutate_descriptor_type(request: ConversationTaskRequest) -> None:
    """Attempt to replace the fixed descriptor type through a low-level setter."""
    # The storage-free descriptor has no writable property backing field, so even
    # object-level assignment cannot reclassify this or another request.
    object.__setattr__(
        request.descriptor,
        "type",
        OpenIdentifier("vendor.changed"),
    )


def test_conversation_task_request_has_fixed_descriptor_and_protocol_shape() -> None:
    """Verify concrete requests implement the complete open task protocol."""
    document = _document()
    request = ConversationTaskRequest(document)
    task_request: ModelTaskRequest = request
    descriptor: TaskDescriptor = request.descriptor

    # Structural protocol compatibility exposes each independent owned value;
    # fixed descriptor fields cannot be inferred from caller document content.
    assert isinstance(request, ModelTaskRequest)
    assert task_request.document is document
    assert task_request.artifacts.artifacts == ()
    assert task_request.metadata == {}
    assert task_request.extensions == {}
    assert descriptor.type == OpenIdentifier("conversation.generate")
    assert descriptor.version is None
    assert descriptor.input_schema_id is None
    assert descriptor.output_schema_id is None
    assert descriptor.metadata == {}
    assert descriptor.extensions == {}

    # Shared descriptor storage is read-only even through a low-level setter.
    _assert_raises(
        AttributeError,
        lambda: _mutate_descriptor_type(request),
        "has no setter",
    )
    assert request.descriptor.type == OpenIdentifier("conversation.generate")


def test_conversation_task_request_preserves_catalog_and_mapping_ownership() -> None:
    """Verify exact Catalog identity and isolated mappings remain observable."""
    artifacts = ArtifactCatalog()
    metadata: dict[str, JsonValue] = {"locale": "zh-CN"}
    extensions: dict[str, JsonValue] = {"vendor.option": {"enabled": True}}
    request = ConversationTaskRequest(
        _document(),
        artifacts=artifacts,
        metadata=metadata,
        extensions=extensions,
    )

    # Catalog is a distinct reference-resolution scope and is not rebuilt. Both
    # mappings detach membership and reject writes after request construction.
    metadata["locale"] = "en"
    extensions["other"] = False
    assert request.artifacts is artifacts
    assert request.metadata == {"locale": "zh-CN"}
    assert request.extensions == {"vendor.option": {"enabled": True}}
    _assert_raises(
        FrozenInstanceError,
        lambda: request.__setattr__("document", _document()),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], request.metadata)),
        "does not support item assignment",
    )


def test_conversation_task_request_constructor_exposes_only_owned_values() -> None:
    """Verify fixed descriptor and nested Message data cannot be injected."""
    constructor_fields = tuple(inspect.signature(ConversationTaskRequest).parameters)

    # Descriptor identity is fixed outside the constructor. Messages and task
    # controls must enter through concrete nodes inside the supplied document.
    assert constructor_fields == (
        "document",
        "artifacts",
        "metadata",
        "extensions",
    )
    for field_name in (
        "descriptor",
        "messages",
        "parameters",
        "target",
        "service_access",
        "authorization",
        "transport",
    ):
        assert field_name not in constructor_fields


def test_conversation_task_request_definition_defers_semantic_validation() -> None:
    """Verify document and recursive JSON semantics remain validator concerns."""
    pending_document = _document(version="", root_kind="vendor.root")
    pending_json = cast(JsonValue, ("not", "portable"))
    request = ConversationTaskRequest(
        pending_document,
        metadata={"pending": pending_json},
    )

    # Construction preserves invalid semantic data without normalization so the
    # following request Validator can retain TaskDocument and JsonValue diagnostics.
    assert request.document is pending_document
    assert request.document.version == ""
    assert request.document.root.kind.id == OpenIdentifier("vendor.root")
    assert request.metadata["pending"] is pending_json


def test_conversation_task_request_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass concrete ownership boundaries."""
    document = _document()
    invalid_cases: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: ConversationTaskRequest(cast(TaskDocument, document.root)),
            "document must be a TaskDocument",
        ),
        (
            lambda: ConversationTaskRequest(
                document,
                artifacts=cast(ArtifactCatalog, None),
            ),
            "artifacts must be an ArtifactCatalog",
        ),
        (
            lambda: ConversationTaskRequest(
                document,
                metadata=cast(Extensions, []),
            ),
            "metadata must be a mapping",
        ),
        (
            lambda: ConversationTaskRequest(
                document,
                metadata=cast(Extensions, {1: True}),
            ),
            "metadata keys must be strings",
        ),
        (
            lambda: ConversationTaskRequest(
                document,
                extensions=cast(Extensions, "invalid"),
            ),
            "extensions must be a mapping",
        ),
    )

    # Each scenario changes one storage boundary only; semantic validation of
    # otherwise well-typed values remains outside the entity constructor.
    for action, message in invalid_cases:
        _assert_raises(TypeError, action, message)
