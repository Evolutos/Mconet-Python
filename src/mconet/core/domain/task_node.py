"""Open structural contract for nodes in a task document tree."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.task_relation import TaskRelation


@runtime_checkable
class TaskNode(Protocol):
    """Describe one task-domain tree node without coupling it to messages.

    Implementations remain structural so integrations can add task-specific node
    kinds without registration or inheritance from an SDK base class. This
    protocol exposes data only; tree consistency, kind composition, ID uniqueness,
    and relation resolution belong to later validators.
    """

    @property
    def id(self) -> str:
        """Return the stable identifier local to the enclosing task document."""
        # Preserve producer identity exactly; uniqueness and non-empty rules need
        # the complete document and therefore cannot be decided by this protocol.
        ...

    @property
    def kind(self) -> TaskNodeKind:
        """Return the open kind describing this node's task semantics."""
        # Expose the kind contract without switching on known identifiers so a
        # custom task node remains representable by older SDK implementations.
        ...

    @property
    def children(self) -> Sequence[TaskNode]:
        """Return child task nodes in stable document order."""
        # Read-only sequence access preserves ordering while allowing custom
        # implementations to choose their own immutable or mutable storage.
        ...

    @property
    def relations(self) -> Sequence[TaskRelation]:
        """Return directed task-node relations in stable declaration order."""
        # Relations remain unresolved references here; only a document-level
        # validator has the complete node index needed to check their endpoints.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return non-control JSON metadata describing this task node."""
        # Metadata is observational data and must not alter kind selection, child
        # traversal, relation direction, or task execution behavior.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned node fields for forward compatibility."""
        # Keeping extensions observable without interpreting them lets newer
        # producers add fields while older consumers preserve the complete node.
        ...
