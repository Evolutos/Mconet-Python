"""Immutable conversation task result backed by one MessageDocument."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.task_descriptor import TaskDescriptor
from mconet.core.domain.task_document import TaskDocument
from mconet.core.domain.task_group_node import TaskGroupNode
from mconet.core.domain.task_node_kind import TaskNodeKind

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_CONVERSATION_TASK_TYPE = OpenIdentifier("conversation.generate")
_CONVERSATION_RESULT_KIND_ID = OpenIdentifier("task.result")
_TASK_ROOT_KIND_ID = OpenIdentifier("task.root")
_RESULT_DOCUMENT_VERSION = "1.0"
_RESULT_NODE_ID = "result"
_RESULT_ROOT_ID = "root"


class _ConversationResultDescriptor:
    """Expose the storage-free fixed descriptor of conversation results."""

    __slots__ = ()

    @property
    def type(self) -> OpenIdentifier:
        """Return the standard conversation generation task identity."""
        # Requests and results share one immutable task identity, preventing a
        # response from silently changing the task family it represents.
        return _CONVERSATION_TASK_TYPE

    @property
    def version(self) -> str | None:
        """Return no producer-specific conversation contract version."""
        # TaskDocument and MessageDocument own their independent Schema versions;
        # the architecture declares no separate descriptor version here.
        return None

    @property
    def input_schema_id(self) -> str | None:
        """Return no external input schema identity for a result descriptor."""
        # A result does not invent request input schema metadata; the common
        # descriptor property remains explicitly absent.
        return None

    @property
    def output_schema_id(self) -> str | None:
        """Return no external output schema identity for the standard result."""
        # Concrete TaskNode and MessageDocument shapes define current result data
        # without fabricating an undeclared external schema identifier.
        return None

    @property
    def metadata(self) -> Extensions:
        """Return empty immutable standard descriptor metadata."""
        # Result-specific facts belong to ConversationTaskResult.metadata and do
        # not alter the fixed task identity shared by all instances.
        return _EMPTY_EXTENSIONS

    @property
    def extensions(self) -> Extensions:
        """Return empty immutable standard descriptor extensions."""
        # Unknown result fields remain on the result itself instead of mutating
        # the canonical conversation task descriptor.
        return _EMPTY_EXTENSIONS


class _ConversationResultKind:
    """Expose the storage-free fixed classification of conversation results."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard task result Kind identifier."""
        # The immutable identifier is shared without exposing writable node Kind
        # state or requiring a public result-node registration mechanism.
        return _CONVERSATION_RESULT_KIND_ID

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the leaf composition fixed for conversation results."""
        # Message elements stay inside MessageDocument and never become TaskNode
        # children during result TaskDocument traversal.
        return "leaf"


class _TaskRootKind:
    """Expose the storage-free standard task document root classification."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard task root Kind identifier."""
        # A canonical immutable ID keeps the generated result document compatible
        # with the shared TaskDocument root invariant.
        return _TASK_ROOT_KIND_ID

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the container composition required for the task root."""
        # The root owns the single conversation result leaf and therefore must
        # remain a container independently from MessageDocument structure.
        return "container"


_CONVERSATION_DESCRIPTOR: TaskDescriptor = _ConversationResultDescriptor()
_CONVERSATION_RESULT_KIND: TaskNodeKind = _ConversationResultKind()
_TASK_ROOT_KIND: TaskNodeKind = _TaskRootKind()


@dataclass(frozen=True, slots=True)
class _ConversationResultNode:
    """Carry one independent MessageDocument inside a task result tree."""

    messages: MessageDocument
    """Complete conversation output document owned by this result leaf."""

    @property
    def id(self) -> str:
        """Return the canonical document-local result node identifier."""
        # One generated document contains exactly one result leaf, so a fixed ID
        # is deterministic and cannot collide with sibling nodes that do not exist.
        return _RESULT_NODE_ID

    @property
    def kind(self) -> TaskNodeKind:
        """Return the fixed ``task.result`` leaf classification."""
        # The shared storage-free Kind cannot be modified per result or inferred
        # from MessageDocument content.
        return _CONVERSATION_RESULT_KIND

    @property
    def children(self) -> tuple[()]:
        """Return the permanently empty TaskNode child sequence."""
        # Message elements remain in their own tree and are deliberately excluded
        # from task traversal and task-node ID indexing.
        return ()

    @property
    def relations(self) -> tuple[()]:
        """Return the permanently empty task relation sequence."""
        # The generated single-node result tree has no task-domain edges; Message
        # relations remain owned by the nested MessageDocument.
        return ()

    @property
    def metadata(self) -> Extensions:
        """Return empty immutable result-node metadata."""
        # Result-level metadata remains on ConversationTaskResult so the internal
        # transport node introduces no duplicate descriptive channel.
        return _EMPTY_EXTENSIONS

    @property
    def extensions(self) -> Extensions:
        """Return empty immutable result-node extensions."""
        # Forward-compatible result fields remain at their public result boundary
        # rather than being hidden in an internal node implementation.
        return _EMPTY_EXTENSIONS


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by result defaults."""
    # Empty data has no nested state and rejects mutation, so sharing avoids an
    # allocation without coupling independently constructed task results.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ConversationTaskResult:
    """Represent one conversation result through an independent message tree.

    ``messages`` is the authoritative conversation output and is embedded once in
    a private conversation-result leaf inside the generated TaskDocument. Message
    elements never become TaskNode children, preserving the independent schemas
    and traversal rules of the Task and Message domains.

    The descriptor is fixed to ``conversation.generate``. The ArtifactCatalog is
    result-local, while metadata and extensions are independent read-only mapping
    membership snapshots. Construction enforces storage shape; complete nested
    semantics remain the responsibility of response validation.
    """

    messages: MessageDocument
    """Independent MessageDocument containing conversation output."""

    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    """Concrete result-local Artifact reference scope."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control result metadata membership snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field membership snapshot for forward compatibility."""

    _document: TaskDocument = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Require owned storage, freeze mappings, and build the result tree."""
        messages = cast(object, self.messages)
        artifacts = cast(object, self.artifacts)

        # Keep MessageDocument nominally independent from its elements and from
        # the TaskDocument that will carry it through the result protocol.
        if not isinstance(messages, MessageDocument):
            raise TypeError(
                "ConversationTaskResult messages must be a MessageDocument."
            )
        # A concrete Catalog distinguishes an empty result scope from missing or
        # unresolved Artifact ownership and prevents cross-request lookup.
        if not isinstance(artifacts, ArtifactCatalog):
            raise TypeError(
                "ConversationTaskResult artifacts must be an ArtifactCatalog."
            )

        # Snapshot both public preservation channels before publishing the frozen
        # result so caller dictionary membership cannot change afterward.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )

        # Build one deterministic task tree containing the MessageDocument exactly
        # once. The fixed task schema version is independent from message.version.
        result_node = _ConversationResultNode(messages)
        root = TaskGroupNode(_RESULT_ROOT_ID, _TASK_ROOT_KIND, (result_node,))
        object.__setattr__(
            self,
            "_document",
            TaskDocument(_RESULT_DOCUMENT_VERSION, root),
        )

    @property
    def descriptor(self) -> TaskDescriptor:
        """Return the fixed ``conversation.generate`` task descriptor."""
        # A shared storage-free descriptor keeps task identity independent from
        # response messages, provider metadata, or Artifact content.
        return _CONVERSATION_DESCRIPTOR

    @property
    def document(self) -> TaskDocument:
        """Return the generated task result document containing ``messages``."""
        # The document is built once during construction and remains authoritative;
        # callers cannot replace it or create a second MessageDocument copy.
        return self._document


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Accept custom Mapping implementations while rejecting arrays, scalars, and
    # keys that cannot represent language-neutral JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"ConversationTaskResult {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"ConversationTaskResult {field_name} keys must be strings.")

    # Preserve exact JsonValue objects and defer recursive semantic checks to the
    # response validator while detaching top-level membership from the caller.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
