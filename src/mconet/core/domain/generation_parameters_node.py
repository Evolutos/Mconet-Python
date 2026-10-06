"""Immutable task configuration leaf carrying generation parameters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.generation_parameters import GenerationParameters
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.task_relation import TaskRelation

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_GENERATION_PARAMETERS_KIND_ID = OpenIdentifier("task.configuration")


class _GenerationParametersKind:
    """Expose the storage-free fixed classification of parameter nodes."""

    __slots__ = ()

    @property
    def id(self) -> OpenIdentifier:
        """Return the standard task configuration Kind identifier."""
        # The immutable identifier and storage-free view are safe to share across
        # every parameter node without exposing per-instance writable state.
        return _GENERATION_PARAMETERS_KIND_ID

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return the leaf composition fixed for parameter nodes."""
        # GenerationParameters is one task configuration value and never becomes
        # a sequence of TaskNode children during document traversal.
        return "leaf"


_GENERATION_PARAMETERS_KIND: TaskNodeKind = _GenerationParametersKind()


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by node defaults."""
    # Empty membership has no nested state and the proxy rejects writes, so one
    # allocation can safely back independent node defaults.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class GenerationParametersNode:
    """Carry generation controls into a task as one fixed configuration leaf.

    The node Kind is always ``task.configuration`` and its TaskNode children are
    always empty. Sampling controls remain grouped in the concrete ``parameters``
    value rather than becoming generic JSON payload or Message data. Protocol
    adapters may later map that value without changing the task tree.

    Construction enforces immutable storage shape only. Node identity, relation
    references, recursive metadata, fixed Kind semantics, and parameter ranges
    belong to the dedicated node, document, and generation validators.
    """

    id: str
    """Stable node identifier local to the enclosing task document."""

    parameters: GenerationParameters
    """Protocol-neutral generation controls carried by this task leaf."""

    relations: tuple[TaskRelation, ...] = ()
    """Directed task relations in exact declaration order."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control node metadata membership snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field membership snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require immutable field shapes and detach mapping membership."""
        node_id = cast(object, self.id)
        parameters = cast(object, self.parameters)
        relations = cast(object, self.relations)

        # Preserve exact identifier text and defer non-empty and document-wide
        # uniqueness rules to validators with the complete task context.
        if not isinstance(node_id, str):
            raise TypeError("GenerationParametersNode id must be a string.")

        # Require the concrete task configuration value so a mapping, Message
        # object, or attribute-compatible substitute cannot erase its boundary.
        if not isinstance(parameters, GenerationParameters):
            raise TypeError(
                "GenerationParametersNode parameters must be GenerationParameters."
            )

        # Relations retain immutable declaration order. Endpoint existence needs
        # the enclosing TaskDocument index and is intentionally deferred.
        if not isinstance(relations, tuple):
            raise TypeError("GenerationParametersNode relations must be a tuple.")
        for relation in cast(tuple[object, ...], relations):
            if not isinstance(relation, TaskRelation):
                raise TypeError(
                    "GenerationParametersNode relations must contain "
                    "TaskRelation values."
                )

        # Snapshot preservation channels independently so later caller mapping
        # mutation cannot alter the frozen node observed by task traversal.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )

    @property
    def kind(self) -> TaskNodeKind:
        """Return the fixed ``task.configuration`` leaf classification."""
        # Sharing a storage-free singleton cannot allow one node to change the
        # Kind identity or composition observed by another parameter node.
        return _GENERATION_PARAMETERS_KIND

    @property
    def children(self) -> tuple[()]:
        """Return the permanently empty TaskNode child sequence."""
        # Individual generation fields belong to the parameters value and are
        # never projected into task traversal or the document node-ID index.
        return ()


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # Mapping admits custom read-only implementations while rejecting values
    # that cannot represent named JSON object membership.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"GenerationParametersNode {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"GenerationParametersNode {field_name} keys must be strings.")

    # Preserve values exactly at construction time. The shared TaskNode validator
    # later owns recursive JSON shape, cycle, integer, and finite-number rules.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
