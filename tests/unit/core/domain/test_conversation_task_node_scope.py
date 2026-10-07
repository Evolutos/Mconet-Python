"""Execution-scope tests for supported conversation TaskNode values."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    ConversationInputNode,
    ConversationTaskRequest,
    Extensions,
    GenerationParameters,
    GenerationParametersNode,
    MessageDocument,
    MessageGroup,
    ModelInteractionError,
    OpenIdentifier,
    TaskDocument,
    TaskGroupNode,
    TaskNode,
    TaskNodeKind,
    TaskRelation,
    validate_conversation_task_node_scope,
)


def _empty_extensions() -> Extensions:
    """Create independent portable mapping storage for test nodes."""
    # Fresh mappings keep IDs, Kinds, metadata, and extensions isolated across
    # success, support-failure, validation-precedence, and mutation scenarios.
    return {}


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide an open task node Kind for fixture trees."""

    id: OpenIdentifier
    """Portable standard or provider-defined node classification."""

    composition: Literal["leaf", "container"]
    """Leaf or container composition used by TaskDocument validation."""


@dataclass(frozen=True, slots=True)
class _MessageKind:
    """Provide the standard root Kind for fixture MessageDocuments."""

    id: OpenIdentifier
    """Portable message element classification."""

    category: str
    """Message-specific element category."""

    composition: Literal["leaf", "container"]
    """Message tree composition used by document validation."""


@dataclass(frozen=True, slots=True)
class _UnknownNode:
    """Represent a valid open TaskNode without supported execution behavior."""

    id: str
    """Task-document-local node identity."""

    kind: TaskNodeKind
    """Open provider-defined or masquerading node Kind."""

    children: Sequence[TaskNode] = ()
    """Ordered child storage used for leaf and container scenarios."""

    relations: Sequence[TaskRelation] = ()
    """Ordered directed task relations."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive node data."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable node fields."""


def _messages(
    purpose: Literal["input", "output", "context", "custom"] = "input",
) -> MessageDocument:
    """Create one empty MessageDocument with a selected valid purpose."""
    # An empty standard root isolates TaskNode support from message-content scope
    # while allowing purpose validation precedence to be tested directly.
    root = MessageGroup(
        "messages",
        _MessageKind(OpenIdentifier("message.root"), "group", "container"),
        (),
    )
    return MessageDocument("1.0", purpose, root)


def _input(
    node_id: str = "input",
    *,
    purpose: Literal["input", "output", "context", "custom"] = "input",
) -> ConversationInputNode:
    """Create one standard conversation input node."""
    # The helper keeps every input field valid except a caller-selected message
    # purpose used to verify complete request validation order.
    return ConversationInputNode(node_id, _messages(purpose))


def _parameters(node_id: str = "parameters") -> GenerationParametersNode:
    """Create one standard generation-parameter node."""
    # A concrete valid value proves this supported leaf retains its own payload
    # identity and does not become a generic or unknown node during traversal.
    return GenerationParametersNode(
        node_id,
        GenerationParameters(max_output_tokens=128),
    )


def _group(group_id: str, *children: TaskNode) -> TaskGroupNode:
    """Create one supported generic task container with ordered children."""
    # A provider-defined group Kind remains supported because TaskGroupNode owns
    # known container behavior independently from the open semantic Kind ID.
    return TaskGroupNode(
        group_id,
        _TaskKind(OpenIdentifier("vendor.section"), "container"),
        children,
    )


def _request(*children: TaskNode) -> ConversationTaskRequest:
    """Create one conversation request around exact root child order."""
    # The concrete standard root is always supported; caller-supplied descendants
    # isolate nested known and unknown node scenarios beneath it.
    root = TaskGroupNode(
        "root",
        _TaskKind(OpenIdentifier("task.root"), "container"),
        children,
    )
    return ConversationTaskRequest(TaskDocument("1.0", root))


def _unknown(
    node_id: str,
    *,
    kind_id: str = "vendor.future",
    composition: Literal["leaf", "container"] = "leaf",
    children: Sequence[TaskNode] = (),
) -> _UnknownNode:
    """Create one valid unsupported node with selected tree semantics."""
    # Supplying Kind and children independently lets tests prove nominal behavior
    # support is not inferred from a standard-looking Kind ID.
    return _UnknownNode(
        id=node_id,
        kind=_TaskKind(OpenIdentifier(kind_id), composition),
        children=children,
        metadata={"fixture": "unknown-node"},
        extensions={"vendor.private": True},
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return an expected exception after matching its diagnostic text."""
    # A narrow boundary prevents fixture construction or unrelated validation
    # failures from accidentally satisfying a support-policy assertion.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_conversation_task_node_scope_accepts_all_supported_nodes() -> None:
    """Verify nested groups, input, and parameters pass without replacement."""
    input_node = _input()
    parameters = _parameters()
    nested = _group("section", input_node, parameters)
    request = _request(nested)
    original_document = request.document
    original_children = nested.children

    # Exact identities and child order prove the gate performs read-only traversal
    # without flattening groups, rebuilding leaves, or normalizing open Kind IDs.
    assert validate_conversation_task_node_scope(request) is request
    assert request.document is original_document
    assert request.document.root.children == (nested,)
    assert nested.children is original_children
    assert nested.children == (input_node, parameters)
    assert nested.kind.id == OpenIdentifier("vendor.section")


def test_conversation_task_node_scope_rejects_unknown_leaf_stably() -> None:
    """Verify one valid open leaf returns the normalized support failure."""
    private_id = "private-node\nsecond-line"
    private_kind = "vendor.private_node"
    unknown = _unknown(private_id, kind_id=private_kind)
    request = _request(_input(), unknown)

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_conversation_task_node_scope(request),
            "Conversation task contains an unsupported TaskNode",
        ),
    )

    # Stable fields remain portable while all producer-controlled node data stays
    # absent from exception text and optional service metadata remains unset.
    assert error.category.id == OpenIdentifier("unsupported_feature")
    assert error.phase.id == OpenIdentifier("validation")
    assert error.code == "unsupported_task_node"
    assert error.message == "Conversation task contains an unsupported TaskNode."
    assert private_id not in str(error)
    assert private_kind not in str(error)
    assert "vendor.private" not in str(error)
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_conversation_task_node_scope_rejects_unknown_container() -> None:
    """Verify an open container stays valid data but is not executable behavior."""
    input_node = _input()
    unknown = _unknown(
        "custom-container",
        composition="container",
        children=[input_node],
    )
    request = _request(unknown)

    # Complete request validation traverses the custom container and finds the one
    # required input; the later support gate still rejects its unknown behavior.
    assert unknown.children == [input_node]
    _assert_raises(
        ModelInteractionError,
        lambda: validate_conversation_task_node_scope(request),
        "unsupported TaskNode",
    )


def test_conversation_task_node_scope_rejects_kind_masquerading() -> None:
    """Verify a standard Kind ID cannot grant behavior to an unknown node."""
    masquerading = _unknown("masquerading", kind_id="task.configuration")
    request = _request(_input(), masquerading)

    # Support is nominal to implemented node behavior. Open Kind identity remains
    # descriptive data and cannot opt arbitrary storage into parameter handling.
    _assert_raises(
        ModelInteractionError,
        lambda: validate_conversation_task_node_scope(request),
        "unsupported TaskNode",
    )


def test_conversation_task_node_scope_preserves_validation_precedence() -> None:
    """Verify malformed known data fails before unknown-node support policy."""
    invalid_input = _input(purpose="output")
    unknown = _unknown("unknown")
    request = _request(invalid_input, unknown)

    # The complete request Validator owns Message purpose and reports its precise
    # error before the execution gate observes the later unknown node.
    _assert_raises(
        ValueError,
        lambda: validate_conversation_task_node_scope(request),
        "messages purpose must be input",
    )


def test_conversation_task_node_scope_rechecks_supported_child_storage() -> None:
    """Verify mutated concrete child storage cannot enter scope traversal."""
    input_node = _input()
    request = _request(input_node)
    object.__setattr__(request.document.root, "children", [input_node])

    # General TaskNode validation admits ordered Sequences for open nodes. The
    # concrete supported-node gate restores TaskGroupNode's tuple invariant at
    # the exact point where execution traversal consumes child membership.
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_node_scope(request),
        "Supported TaskNode children must be a tuple",
    )


def test_conversation_task_node_scope_requires_standard_request() -> None:
    """Verify unrelated objects fail through the complete request boundary."""
    # The scope gate accepts only the concrete standard request whose fixed task
    # identity and composition Validator define this execution profile.
    _assert_raises(
        TypeError,
        lambda: validate_conversation_task_node_scope(
            cast(ConversationTaskRequest, object())
        ),
        "request must be a ConversationTaskRequest",
    )
