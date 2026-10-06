"""Pre-I/O composition tests for ModelRequest validation."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationInputNode,
    ConversationTaskRequest,
    Extensions,
    HeaderField,
    Headers,
    MessageDocument,
    MessageElementKind,
    MessageEntry,
    MessageGroup,
    MessageRole,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TextMessageContent,
    UriValue,
    validate_model_request,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide an open task node Kind for request fixtures."""

    id: OpenIdentifier
    """Open node Kind identity."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide an open message element Kind for request fixtures."""

    id: OpenIdentifier
    """Open message element Kind identity."""

    category: str
    """Open message element classification category."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition."""


@dataclass(frozen=True, slots=True)
class _Role:
    """Provide an open message role implementation."""

    id: OpenIdentifier
    """Open message role identity."""

    semantic: str | None
    """Optional producer guidance for the role meaning."""

    raw_value: str | None
    """Optional original external role spelling."""

    extensions: Extensions
    """Unknown role fields preserved for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Provide a complete application-owned model target."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected interaction protocol identity."""

    model: NamedModel
    """Selected provider-facing model descriptor."""

    deployment_id: str | None
    """Optional service-side deployment identity."""

    extensions: Extensions
    """Unknown target fields preserved for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _Access:
    """Provide complete unresolved per-request service access input."""

    endpoint: UriValue | None
    """Optional absolute service endpoint."""

    authorization: None
    """Explicitly unresolved authorization input."""

    headers: Headers
    """Ordered ordinary request headers."""

    query: QueryParameters
    """Ordered ordinary query parameters."""

    api_version: str | None
    """Optional provider API version."""

    project_id: str | None
    """Optional provider project identity."""

    tenant_id: str | None
    """Optional provider tenant identity."""

    extensions: Extensions
    """Unknown access fields preserved for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Provide a complete descriptor for an application-owned task."""

    type: OpenIdentifier
    """Open task identity."""

    version: str | None
    """Optional task contract version."""

    input_schema_id: str | None
    """Optional task input schema identity."""

    output_schema_id: str | None
    """Optional task output schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields preserved for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _OpenTaskRequest:
    """Provide a non-conversation ModelTaskRequest implementation."""

    descriptor: TaskDescriptor
    """Open task identity and schema contract."""

    document: TaskDocument
    """Versioned task input and control tree."""

    artifacts: ArtifactCatalog
    """Request-local Artifact reference scope."""

    metadata: Extensions
    """Portable task request metadata."""

    extensions: Extensions
    """Unknown task fields preserved for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _Request:
    """Provide a complete application-owned ModelRequest implementation."""

    target: ModelTarget
    """Independent model interaction target."""

    task: ModelTaskRequest
    """Independent open task request."""

    service_access: ServiceAccess | None
    """Optional unresolved access override for this request."""

    metadata: Extensions
    """Portable request-level descriptive data."""

    extensions: Extensions
    """Unknown request fields preserved for forward compatibility."""


def _assert_raises(
    error_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Run one action and return the expected exception with stable text."""
    # Keep assertions independent from a third-party matcher while checking that
    # validation fails at the intended composed boundary rather than incidentally.
    try:
        action()
    except error_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {error_type.__name__} containing {message!r}.")


def _set_field(value: object, field_name: str, replacement: object) -> None:
    """Inject an impossible decoded value into one frozen test record."""
    # Public constructors and static types prevent malformed states. Controlled
    # mutation exercises defensive validation of external runtime implementations.
    object.__setattr__(value, field_name, replacement)


def _target() -> _Target:
    """Create one valid open model target."""
    # Separate service, protocol, model, and deployment values ensure validation
    # observes the complete target instead of deriving one dimension from another.
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
        "primary",
        MappingProxyType({"routingHint": "east"}),
    )


def _access() -> _Access:
    """Create one valid unresolved per-request access value."""
    # The fixture includes ordinary context while deliberately leaving
    # authorization unresolved for a later configuration resolution layer.
    return _Access(
        UriValue("https://models.example.test/v1", is_absolute=True),
        None,
        Headers((HeaderField("X-Feature", "enabled"),)),
        QueryParameters((QueryParameter("region", "east"),)),
        "2026-10-01",
        "project-a",
        "tenant-a",
        MappingProxyType({"accessOption": True}),
    )


def _task_root(*children: TaskNode, version: str = "1.0") -> TaskDocument:
    """Create one task document around an exact ordered child sequence."""
    # Exact TaskNode typing keeps every fixture inside the public document
    # boundary while callers vary only child order and document version.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    return TaskDocument(
        version,
        TaskGroupNode(
            "root",
            kind,
            children,
        ),
    )


def _conversation_task() -> ConversationTaskRequest:
    """Create one valid text-only conversation task request."""
    # A single user entry inside one input MessageDocument satisfies the concrete
    # task composition without introducing parameters or Artifact data.
    role: MessageRole = _Role(
        OpenIdentifier("message.user"),
        "user",
        "user",
        MappingProxyType({}),
    )
    entry = MessageEntry(
        "entry",
        role,
        (TextMessageContent("content", "hello"),),
    )
    message_kind: MessageElementKind = _MessageKind(
        OpenIdentifier("message.root"),
        "group",
        "container",
    )
    messages = MessageDocument(
        "1.0",
        "input",
        MessageGroup("message-root", message_kind, (entry,)),
    )
    input_node = ConversationInputNode("input", messages)
    return ConversationTaskRequest(
        _task_root(input_node),
        metadata=MappingProxyType({"taskLabel": "conversation"}),
        extensions=MappingProxyType({"taskOption": True}),
    )


def _open_task() -> _OpenTaskRequest:
    """Create one valid application-owned non-conversation task request."""
    # The open task proves common validation does not depend on a known concrete
    # request class or prematurely enforce supported task-type policy.
    descriptor: TaskDescriptor = _Descriptor(
        OpenIdentifier("vendor.embedding"),
        "2026.10",
        "schema.vendor.input",
        "schema.vendor.output",
        MappingProxyType({"owner": "application"}),
        MappingProxyType({"descriptorOption": True}),
    )
    return _OpenTaskRequest(
        descriptor,
        _task_root(),
        ArtifactCatalog(),
        MappingProxyType({"taskLabel": "embedding"}),
        MappingProxyType({"taskOption": {"enabled": True}}),
    )


def _request(
    *,
    target: ModelTarget | None = None,
    task: ModelTaskRequest | None = None,
    access: ServiceAccess | None = None,
) -> _Request:
    """Create one complete model request with selected composed values."""
    # None selects a fresh valid fixture; callers can still represent explicit
    # missing request-level access by assigning that field after construction.
    return _Request(
        target if target is not None else _target(),
        task if task is not None else _conversation_task(),
        access if access is not None else _access(),
        MappingProxyType({"traceLabel": "request-a"}),
        MappingProxyType({"requestOption": [1, True, None]}),
    )


def test_validator_accepts_complete_conversation_request() -> None:
    """Verify Target, known Task, Access, and JSON compose without rebuilding."""
    target = _target()
    task = _conversation_task()
    access = _access()
    request = _request(target=target, task=task, access=access)

    # Successful validation preserves the application-owned envelope and exact
    # identities of every independently owned composed domain value.
    assert validate_model_request(request) is request
    assert request.target is target
    assert request.task is task
    assert request.service_access is access


def test_validator_accepts_open_task_and_missing_access_override() -> None:
    """Verify unknown valid tasks remain open and request access may be absent."""
    task = _open_task()
    request = _request(task=task)
    _set_field(request, "service_access", None)

    # Common task values are validated, but support policy remains separate;
    # None stays unresolved rather than becoming synthesized anonymous access.
    assert validate_model_request(request) is request
    assert request.task is task
    assert request.service_access is None


def test_validator_rejects_incomplete_request_surface() -> None:
    """Verify an arbitrary object cannot enter composed domain validation."""
    _assert_raises(
        TypeError,
        lambda: validate_model_request(cast(ModelRequest, object())),
        "request must implement ModelRequest",
    )


def test_validator_delegates_target_before_later_domains() -> None:
    """Verify invalid routing fails before malformed task or access values."""
    target = _target()
    request = _request(target=target)
    _set_field(target, "service_id", "not-an-identifier")
    _set_field(request, "task", object())
    _set_field(request, "service_access", object())

    # Stable ordering reports the target-local nominal failure without inspecting
    # later task or access fields and without attempting any resolution or I/O.
    _assert_raises(
        TypeError,
        lambda: validate_model_request(request),
        "ModelTarget service_id must be an OpenIdentifier",
    )


def test_validator_requires_a_complete_task_and_delegates_conversation_rules() -> None:
    """Verify task nominal shape and known composition fail independently."""
    wrong_task = _request()
    _set_field(wrong_task, "task", object())
    _assert_raises(
        TypeError,
        lambda: validate_model_request(wrong_task),
        "task must implement ModelTaskRequest",
    )

    conversation = ConversationTaskRequest(_task_root())
    invalid_conversation = _request(task=conversation)
    # The known task validator owns input-node cardinality and retains its exact
    # diagnostic instead of being replaced by an outer request failure.
    _assert_raises(
        ValueError,
        lambda: validate_model_request(invalid_conversation),
        "must contain exactly one ConversationInputNode",
    )


def test_validator_delegates_every_open_task_domain() -> None:
    """Verify descriptor, document, catalog, and JSON remain independently owned."""
    invalid_descriptor = _open_task()
    _set_field(invalid_descriptor.descriptor, "version", "")
    _assert_raises(
        ValueError,
        lambda: validate_model_request(_request(task=invalid_descriptor)),
        "TaskDescriptor version must not be empty",
    )

    invalid_document = _open_task()
    _set_field(invalid_document, "document", _task_root(version=""))
    _assert_raises(
        ValueError,
        lambda: validate_model_request(_request(task=invalid_document)),
        "TaskDocument version must not be empty",
    )

    invalid_catalog = _open_task()
    _set_field(invalid_catalog, "artifacts", object())
    _assert_raises(
        TypeError,
        lambda: validate_model_request(_request(task=invalid_catalog)),
        "catalog must be an ArtifactCatalog",
    )

    invalid_metadata = _open_task()
    _set_field(invalid_metadata, "metadata", [])
    _assert_raises(
        TypeError,
        lambda: validate_model_request(_request(task=invalid_metadata)),
        "task metadata must be a mapping",
    )

    invalid_extensions = _open_task()
    _set_field(invalid_extensions, "extensions", {1: "invalid-key"})
    _assert_raises(
        TypeError,
        lambda: validate_model_request(_request(task=invalid_extensions)),
        "task extensions keys must be strings",
    )


def test_validator_delegates_optional_access_validation() -> None:
    """Verify present request-level access receives its complete domain checks."""
    wrong_access = _request()
    _set_field(wrong_access, "service_access", object())
    _assert_raises(
        TypeError,
        lambda: validate_model_request(wrong_access),
        "access must implement ServiceAccess",
    )

    access = _access()
    _set_field(access, "api_version", 1)
    request = _request(access=access)

    # Nominal access shape is checked before provider context semantics, and the
    # shared access validator retains its own precise diagnostic at both levels.
    _assert_raises(
        TypeError,
        lambda: validate_model_request(request),
        "ServiceAccess api_version must be a string or None",
    )


def test_validator_requires_portable_request_json_channels() -> None:
    """Verify request metadata and extensions enforce object and JSON semantics."""
    invalid_metadata = _request()
    _set_field(invalid_metadata, "metadata", [])
    _assert_raises(
        TypeError,
        lambda: validate_model_request(invalid_metadata),
        "metadata must be a mapping",
    )

    invalid_keys = _request()
    _set_field(invalid_keys, "extensions", {1: "invalid-key"})
    _assert_raises(
        TypeError,
        lambda: validate_model_request(invalid_keys),
        "extensions keys must be strings",
    )

    invalid_value = _request()
    _set_field(invalid_value, "metadata", {"score": math.inf})
    # Delegate recursive JSON rules so request fields share the same finite-number
    # contract as target, task, access, and all other cross-platform data.
    _assert_raises(
        ValueError,
        lambda: validate_model_request(invalid_value),
        "JSON floating-point value must be finite",
    )
