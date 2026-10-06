"""Open structural contract for one model task result."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.task_descriptor import TaskDescriptor
from mconet.core.domain.task_document import TaskDocument


@runtime_checkable
class ModelTaskResult(Protocol):
    """Describe one extensible task result and its owned artifact scope.

    Implementations expose task identity, a result document, a result-local
    ArtifactCatalog, descriptive metadata, and preserved extension fields as
    independent values. The structural contract permits future task families to
    provide result types without SDK inheritance or registration.

    Request inputs, interaction target, resolved model, output status, usage,
    diagnostics, protocol state, and transport details belong to enclosing
    request, parsed-response, or output contracts and are intentionally absent.
    """

    @property
    def descriptor(self) -> TaskDescriptor:
        """Return the open descriptor naming this task result contract."""
        # Task identity remains separate from result-tree representation so
        # consumers never infer the result type from concrete node contents.
        ...

    @property
    def document(self) -> TaskDocument:
        """Return the versioned document containing task result nodes."""
        # The complete result tree is one owned value; task-specific projections
        # may read it but cannot replace this authoritative document.
        ...

    @property
    def artifacts(self) -> ArtifactCatalog:
        """Return the result-local catalog used by result artifact references."""
        # This concrete scope belongs only to the result and cannot implicitly
        # search the originating request, client, session, or another result.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return portable descriptive metadata for this task result."""
        # Metadata carries result facts only and cannot configure execution,
        # authorization, transport, target selection, status, or diagnostics.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown result fields retained for forward compatibility."""
        # Extensions preserve producer-owned JsonValue data without promoting it
        # into descriptor, document, Artifact, metadata, or runtime semantics.
        ...
