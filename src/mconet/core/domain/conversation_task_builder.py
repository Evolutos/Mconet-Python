"""Fluent construction for validated immutable conversation task requests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Self, cast

from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.conversation_task_request import ConversationTaskRequest
from mconet.core.domain.conversation_task_request_validation import (
    validate_conversation_task_request,
)
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.task_document import TaskDocument


class ConversationTaskBuilder:
    """Accumulate fields for one validated conversation task request.

    The required :class:`TaskDocument` remains caller-owned and retains the
    complete ordered task tree. Artifact scope, metadata, and extensions map
    directly to the remaining :class:`ConversationTaskRequest` constructor
    fields. Every :meth:`build` call creates a fresh immutable request and
    delegates all document, message, parameter, Artifact, and JSON semantics to
    :func:`validate_conversation_task_request`.

    This builder constructs only the task-level domain value. Model targets,
    service access, interaction options, protocol components, and I/O belong to
    later request and runtime layers. The mutable builder is intentionally not
    thread-safe; completed immutable requests may be shared normally.
    """

    __slots__ = (
        "_artifacts",
        "_document",
        "_extensions",
        "_metadata",
    )

    def __init__(self, document: TaskDocument) -> None:
        """Start a builder with the complete required task document.

        Args:
            document: Versioned conversation task tree retained by identity.

        Raises:
            TypeError: If ``document`` is not a concrete :class:`TaskDocument`.
        """
        candidate = cast(object, document)
        # Reject an invalid storage boundary before mutable builder state exists.
        # Complete tree and payload semantics remain validator-owned at build().
        if not isinstance(candidate, TaskDocument):
            raise TypeError("ConversationTaskBuilder document must be a TaskDocument.")

        # Retain the immutable document exactly. Each builder owns fresh default
        # containers so independent construction flows cannot share mutable state.
        self._document = candidate
        self._artifacts = ArtifactCatalog()
        self._metadata: dict[str, JsonValue] = {}
        self._extensions: dict[str, JsonValue] = {}

    def with_artifacts(self, artifacts: ArtifactCatalog) -> Self:
        """Replace the request-local Artifact scope.

        Args:
            artifacts: Concrete catalog used to resolve request references.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``artifacts`` is not an :class:`ArtifactCatalog`.
        """
        candidate = cast(object, artifacts)
        # Validate before replacement so a failed fluent call leaves the prior
        # builder state intact. Catalog semantics remain the request validator's
        # responsibility because it has the complete task and support scope.
        if not isinstance(candidate, ArtifactCatalog):
            raise TypeError(
                "ConversationTaskBuilder artifacts must be an ArtifactCatalog."
            )
        self._artifacts = candidate
        return self

    def with_metadata(self, metadata: Extensions) -> Self:
        """Replace descriptive request metadata with an owned snapshot.

        Args:
            metadata: String-keyed portable JSON metadata.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``metadata`` is not a string-keyed mapping.
        """
        # Snapshot membership at the fluent boundary so later caller mutation
        # cannot change a request produced from the builder's current state.
        self._metadata = _snapshot_mapping(metadata, "metadata")
        return self

    def with_extensions(self, extensions: Extensions) -> Self:
        """Replace unknown request fields with an owned snapshot.

        Args:
            extensions: String-keyed forward-compatible JSON fields.

        Returns:
            This builder for fluent construction.

        Raises:
            TypeError: If ``extensions`` is not a string-keyed mapping.
        """
        # Keep unknown fields isolated from metadata in their own owned mapping;
        # neither channel may become task input, configuration, or access data.
        self._extensions = _snapshot_mapping(extensions, "extensions")
        return self

    def build(self) -> ConversationTaskRequest:
        """Create and validate a fresh immutable conversation task request.

        Returns:
            A request equivalent to direct ``ConversationTaskRequest``
            construction with the builder's current fields.

        Raises:
            TypeError: If a stored field or nested value has an invalid shape.
            ValueError: If task, message, parameter, or JSON semantics are invalid.
            ModelInteractionError: If content or Artifacts exceed the currently
                supported conversation request scope.
        """
        # The immutable request snapshots both mapping channels while retaining
        # exact TaskDocument and ArtifactCatalog identities. Later builder changes
        # therefore cannot modify a request that has already been returned.
        request = ConversationTaskRequest(
            self._document,
            artifacts=self._artifacts,
            metadata=self._metadata,
            extensions=self._extensions,
        )
        # Reuse the complete request validator as the sole semantic authority;
        # this builder deliberately owns no parallel task or support rules.
        return validate_conversation_task_request(request)


def _snapshot_mapping(value: Extensions, field_name: str) -> dict[str, JsonValue]:
    """Return owned string-keyed membership without interpreting JSON values."""
    candidate = cast(object, value)
    # Accept any Mapping implementation while enforcing the language-neutral
    # object boundary that requires string keys at the fluent call site.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"ConversationTaskBuilder {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"ConversationTaskBuilder {field_name} keys must be strings.")

    # Preserve values exactly and defer recursive JSON, cycle, finite-number,
    # and safe-integer rules to the existing request validator during build().
    return dict(cast(Mapping[str, JsonValue], source))
