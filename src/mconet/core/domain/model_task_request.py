"""Open structural contract for one model task request."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.task_descriptor import TaskDescriptor
from mconet.core.domain.task_document import TaskDocument


@runtime_checkable
class ModelTaskRequest(Protocol):
    """Describe one extensible task request and its owned artifact scope.

    Implementations expose task identity, the task tree, request-local artifacts,
    descriptive metadata, and preserved extension fields as independent values.
    The protocol contains data only and requires no SDK inheritance or task-type
    registration, allowing future task families to provide concrete requests.

    Message documents may appear only inside task-specific nodes. Interaction
    targets, access configuration, credentials, protocol payloads, and transport
    state belong to outer request or runtime contracts and are intentionally
    absent from this task boundary.
    """

    @property
    def descriptor(self) -> TaskDescriptor:
        """Return the open descriptor naming this task contract."""
        # Task identity remains separate from tree representation so adapters can
        # select behavior without inferring type or schema from document contents.
        ...

    @property
    def document(self) -> TaskDocument:
        """Return the versioned document containing task inputs and controls."""
        # The complete task tree is one owned value; message data, when relevant,
        # remains nested in a concrete node rather than replacing this document.
        ...

    @property
    def artifacts(self) -> ArtifactCatalog:
        """Return the request-local catalog used for artifact references."""
        # An empty concrete catalog represents no artifacts. None must not also
        # mean unresolved scope, and references cannot search outside this value.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return portable descriptive metadata for this request."""
        # Metadata carries non-control facts only and cannot configure execution,
        # authorization, transport, or target protocol behavior.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown request fields retained for forward compatibility."""
        # Extensions preserve producer-owned JsonValue data without promoting it
        # into descriptor, document, artifact, metadata, or runtime semantics.
        ...
