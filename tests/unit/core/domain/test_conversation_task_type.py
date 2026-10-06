"""Execution-scope tests for the supported conversation task identity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    ConversationInputNode,
    ConversationTaskRequest,
    Extensions,
    MessageDocument,
    MessageGroup,
    ModelInteractionError,
    ModelTaskRequest,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    validate_conversation_task_type,
)


def _empty_extensions() -> Extensions:
    """Create independent portable mapping storage for test values."""
    # Fresh dictionaries prevent dynamic mutation in one scenario from changing
    # another descriptor, task request, message tree, or assertion.
    return {}


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide an open task node Kind for fixture trees."""

    id: OpenIdentifier
    """Portable standard or provider-defined task Kind identity."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition used by TaskDocument validation."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide a complete message group Kind for input documents."""

    id: OpenIdentifier
    """Portable message element Kind identity."""

    category: str
    """Open message-specific element category."""

    composition: Literal["leaf", "container"]
    """Message tree composition used by document validation."""


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Provide an application-owned open task descriptor."""

    type: OpenIdentifier
    """Task identity selected by the caller."""

    version: str | None = None
    """Optional producer task contract version."""

    input_schema_id: str | None = None
    """Optional task input schema identity."""

    output_schema_id: str | None = None
    """Optional task output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive descriptor data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable descriptor data."""


@dataclass(frozen=True, slots=True)
class _OpenTask:
    """Provide a complete application-owned ModelTaskRequest implementation."""

    descriptor: TaskDescriptor
    """Open task identity and schema declaration."""

    document: TaskDocument
    """Versioned task tree retained without interpretation by this gate."""

    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    """Concrete request-local Artifact reference scope."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable task request metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable task request data."""


def _task_root(children: tuple[ConversationInputNode, ...] = ()) -> TaskGroupNode:
    """Create one standard task root around ordered fixture children."""
    # A concrete immutable root makes both standard and application-owned tasks
    # valid common-domain values without involving protocol or Runtime behavior.
    return TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        children,
    )


def _messages(purpose: str = "input") -> MessageDocument:
    """Create one empty message document with a caller-selected purpose."""
    # The empty standard root isolates task-type selection from content behavior;
    # a custom purpose is used only to exercise composed request validation.
    root = MessageGroup(
        "messages",
        _MessageKind(OpenIdentifier("message.root"), "group", "container"),
        (),
    )
    return MessageDocument(
        "1.0",
        cast(Literal["input", "output", "context", "custom"], purpose),
        root,
    )


def _conversation_request(*, purpose: str = "input") -> ConversationTaskRequest:
    """Create one standard conversation request with a single input node."""
    # One input node satisfies the concrete conversation cardinality contract and
    # makes failures attributable to the caller-selected Message purpose alone.
    input_node = ConversationInputNode("input", _messages(purpose))
    return ConversationTaskRequest(TaskDocument("1.0", _task_root((input_node,))))


def _open_task(task_type: str) -> _OpenTask:
    """Create one valid open task using the exact supplied type identity."""
    # The same document and Artifact shape across task types ensures the support
    # result depends only on the validated descriptor identity.
    return _OpenTask(
        descriptor=_Descriptor(OpenIdentifier(task_type)),
        document=TaskDocument("1.0", _task_root()),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return an expected exception after matching its diagnostic text."""
    # A narrow boundary prevents setup or structural failures from accidentally
    # satisfying an assertion intended for task support policy.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_conversation_task_type_accepts_standard_request_by_identity() -> None:
    """Verify a valid standard conversation request passes without replacement."""
    request = _conversation_request()
    original_descriptor = request.descriptor
    original_document = request.document

    # Exact identity proves the gate neither rebuilds the request nor normalizes
    # its fixed descriptor, document, input MessageDocument, or Artifact scope.
    assert validate_conversation_task_type(request) is request
    assert request.descriptor is original_descriptor
    assert request.document is original_document
    input_node = request.document.root.children[0]
    assert isinstance(input_node, ConversationInputNode)
    assert input_node.messages.purpose == "input"


def test_conversation_task_type_accepts_open_matching_implementation() -> None:
    """Verify support follows descriptor identity rather than concrete class."""
    task = _open_task("conversation.generate")

    # Application-owned task implementations remain open after common request
    # validation; the support gate only selects the exact task type it owns.
    assert isinstance(task, ModelTaskRequest)
    assert not isinstance(task, ConversationTaskRequest)
    assert validate_conversation_task_type(task) is task


def test_conversation_task_type_rejects_nonconversation_types_stably() -> None:
    """Verify standard and unknown task types return one normalized failure."""
    private_type = "vendor.private_task"
    for task_type in ("embedding.create", private_type):
        task = _open_task(task_type)
        error = cast(
            ModelInteractionError,
            _assert_raises(
                ModelInteractionError,
                lambda task=task: validate_conversation_task_type(task),
                "Only conversation.generate tasks are supported",
            ),
        )

        # Stable language-neutral fields do not expose provider-controlled type,
        # descriptor metadata, task document, or Artifact information.
        assert error.category.id == OpenIdentifier("unsupported_feature")
        assert error.phase.id == OpenIdentifier("validation")
        assert error.code == "unsupported_task"
        assert error.message == "Only conversation.generate tasks are supported."
        assert private_type not in str(error)
        assert error.status_code is None
        assert error.service_error_code is None
        assert error.request_id is None
        assert error.recovery is None
        assert error.cause is None


def test_conversation_task_type_preserves_descriptor_error_precedence() -> None:
    """Verify malformed descriptors fail before task support policy."""
    task = _open_task("vendor.valid")
    object.__setattr__(task.descriptor, "type", OpenIdentifier("Invalid Type"))

    # OpenIdentifier construction preserves raw text; the shared descriptor
    # validator must report its grammar failure rather than unsupported_task.
    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_type(task),
        "OpenIdentifier",
    )


def test_conversation_task_type_composes_standard_request_validation() -> None:
    """Verify malformed known conversation data fails before successful return."""
    request = _conversation_request(purpose="output")

    # Type identity is supported, but the known concrete request must still cross
    # its sole composed Validator before any later adapter or I/O stage can run.
    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_type(request),
        "messages purpose must be input",
    )


def test_conversation_task_type_requires_complete_task_protocol() -> None:
    """Verify partial and unrelated objects fail before descriptor access."""
    partial = _Descriptor(OpenIdentifier("conversation.generate"))

    # A descriptor alone cannot masquerade as a task request even though its type
    # would otherwise match the supported identity exactly.
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_type(cast(ModelTaskRequest, partial)),
        "task must implement ModelTaskRequest",
    )
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_type(cast(ModelTaskRequest, object())),
        "task must implement ModelTaskRequest",
    )
