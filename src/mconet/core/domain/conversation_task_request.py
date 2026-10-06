"""Immutable model task request with fixed conversation generation identity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.task_descriptor import TaskDescriptor
from mconet.core.domain.task_document import TaskDocument

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_CONVERSATION_TASK_TYPE = OpenIdentifier("conversation.generate")


class _ConversationTaskDescriptor:
    """Expose the storage-free fixed descriptor of conversation generation."""

    __slots__ = ()

    @property
    def type(self) -> OpenIdentifier:
        """Return the standard conversation generation task identity."""
        # The immutable identifier and storage-free view are safe to share across
        # all conversation requests without caller-controlled reclassification.
        return _CONVERSATION_TASK_TYPE

    @property
    def version(self) -> str | None:
        """Return no producer-specific conversation contract version."""
        # TaskDocument owns its own schema version. No separate descriptor version
        # is declared by the architecture, so absence remains explicit.
        return None

    @property
    def input_schema_id(self) -> str | None:
        """Return no external input schema identity for the standard task."""
        # Concrete TaskNode and MessageDocument validators define input semantics
        # without inventing an undeclared schema identifier.
        return None

    @property
    def output_schema_id(self) -> str | None:
        """Return no external output schema identity for the standard task."""
        # Response constraints and task result contracts remain separate from the
        # descriptor and cannot be inferred into an output schema identifier.
        return None

    @property
    def metadata(self) -> Extensions:
        """Return empty immutable standard descriptor metadata."""
        # Request metadata remains independently caller-owned; fixed task identity
        # carries no implicit descriptive facts.
        return _EMPTY_EXTENSIONS

    @property
    def extensions(self) -> Extensions:
        """Return empty immutable standard descriptor extensions."""
        # Unknown request fields belong to ConversationTaskRequest.extensions and
        # cannot silently alter the fixed descriptor contract.
        return _EMPTY_EXTENSIONS


_CONVERSATION_DESCRIPTOR: TaskDescriptor = _ConversationTaskDescriptor()


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by request defaults."""
    # The proxy contains no nested state and rejects mutation, so sharing avoids
    # allocation without coupling independently constructed requests.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ConversationTaskRequest:
    """Represent one conversation generation task with a fixed descriptor.

    The descriptor always identifies ``conversation.generate``. The TaskDocument
    carries conversation input, generation configuration, and future task nodes;
    the ArtifactCatalog supplies the request-local reference scope. Message data
    may enter only through ConversationInputNode inside ``document``.

    Construction enforces immutable storage shape only. Descriptor semantics,
    document composition, message scope, parameter scope, artifact validity, and
    recursive JSON rules belong to the dedicated request validator.
    """

    document: TaskDocument
    """Versioned task tree containing conversation input and configuration."""

    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    """Concrete request-local artifact scope; empty rather than absent by default."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control request metadata membership snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field membership snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require concrete owned values and detach mapping membership."""
        document = cast(object, self.document)
        artifacts = cast(object, self.artifacts)

        # Require the complete versioned task tree rather than accepting a root
        # node or MessageDocument that would erase the task document boundary.
        if not isinstance(document, TaskDocument):
            raise TypeError("ConversationTaskRequest document must be a TaskDocument.")

        # A concrete catalog distinguishes the resolved empty scope from missing
        # or unresolved state and prevents implicit cross-request artifact lookup.
        if not isinstance(artifacts, ArtifactCatalog):
            raise TypeError(
                "ConversationTaskRequest artifacts must be an ArtifactCatalog."
            )

        # Snapshot both preservation channels independently so later source-map
        # mutation cannot alter the frozen request observed by adapters.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )

    @property
    def descriptor(self) -> TaskDescriptor:
        """Return the fixed ``conversation.generate`` task descriptor."""
        # A shared storage-free descriptor cannot be modified per request, keeping
        # task selection independent from document contents or caller metadata.
        return _CONVERSATION_DESCRIPTOR


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Mapping admits custom read-only sources while excluding values that cannot
    # represent named JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"ConversationTaskRequest {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"ConversationTaskRequest {field_name} keys must be strings.")

    # Preserve values exactly at construction time. Recursive JSON validation is
    # deferred so the request validator owns stable semantic diagnostics.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
