"""Immutable root document for one ordered task node tree."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.task_group_node import TaskGroupNode

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by document defaults."""
    # No nested state exists in the empty proxy, so sharing it avoids allocations
    # without allowing one document to mutate another document's default data.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class TaskDocument:
    """Own one versioned task tree independently from message and access data.

    ``version`` retains exact producer text and ``root`` is the sole entry point
    into ordered TaskNode traversal. Descriptive metadata and forward-compatible
    extensions remain separate JSON channels. The document never carries message
    roles or content, authorization, service endpoints, transport settings, or
    protocol payloads.

    Construction enforces immutable storage shape only. Version grammar, root
    semantics, recursive node validation, global ID uniqueness, relation
    resolution, and cycle detection belong to the dedicated validator.
    """

    version: str
    """Exact task document schema version text."""

    root: TaskGroupNode
    """Concrete root group that owns the ordered task node tree."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control document metadata membership snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field membership snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require primitive field shapes and detach mapping membership."""
        version = cast(object, self.version)
        root = cast(object, self.root)

        # Preserve original version text and defer its semantic rules so the
        # validator can report stable failures without normalizing producer data.
        if not isinstance(version, str):
            raise TypeError("TaskDocument version must be a string.")

        # Require the concrete immutable group instead of accepting an arbitrary
        # TaskNode that merely resembles a possible document root.
        if not isinstance(root, TaskGroupNode):
            raise TypeError("TaskDocument root must be a TaskGroupNode.")

        # Snapshot both JSON channels independently so caller membership changes
        # cannot modify the frozen document after construction.
        object.__setattr__(
            self, "metadata", _snapshot_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "extensions",
            _snapshot_mapping(self.extensions, "extensions"),
        )


def _snapshot_mapping(value: Extensions, field_name: str) -> Extensions:
    """Copy one string-keyed mapping and expose read-only membership."""
    candidate = cast(object, value)
    # The public contract admits any Mapping implementation while JSON object
    # membership remains string-keyed across every supported language.
    if not isinstance(candidate, Mapping):
        raise TypeError(f"TaskDocument {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"TaskDocument {field_name} keys must be strings.")

    # Preserve values exactly and leave recursive JSON and numeric policy to the
    # document validator while detaching top-level membership from the caller.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
