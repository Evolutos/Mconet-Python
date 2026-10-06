"""Immutable root document for one ordered message element tree."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.message_group import MessageGroup

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty mapping used by document defaults."""
    # No nested state exists in the empty proxy, so sharing it avoids allocations
    # without allowing one document to mutate another document's default data.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class MessageDocument:
    """Own one versioned message tree independently from task and access data.

    ``version`` retains exact producer text, ``purpose`` states why the message
    tree exists, and ``root`` is the sole entry point into ordered MessageElement
    traversal. Descriptive metadata and forward-compatible extensions remain
    separate JSON channels. The document never carries task parameters,
    authorization, service endpoints, transport settings, or protocol payloads.

    Construction enforces immutable storage shape only. Version grammar,
    purpose membership, root semantics, recursive element validation, global ID
    uniqueness, and relation resolution belong to the dedicated validator.
    """

    version: str
    """Exact message document schema version text."""

    purpose: Literal["input", "output", "context", "custom"]
    """Declared input, output, context, or custom document purpose."""

    root: MessageGroup
    """Concrete root group that owns the ordered message element tree."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-control document metadata snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown-field snapshot for forward compatibility."""

    def __post_init__(self) -> None:
        """Require primitive field shapes and detach mapping membership."""
        version = cast(object, self.version)
        purpose = cast(object, self.purpose)
        root = cast(object, self.root)

        # Preserve original text and defer version/purpose semantic rules so a
        # validator can report stable field-specific failures without normalization.
        if not isinstance(version, str):
            raise TypeError("MessageDocument version must be a string.")
        if not isinstance(purpose, str):
            raise TypeError("MessageDocument purpose must be a string.")

        # Require the concrete immutable group value instead of accepting an
        # arbitrary MessageElement that merely resembles a possible tree root.
        if not isinstance(root, MessageGroup):
            raise TypeError("MessageDocument root must be a MessageGroup.")

        # Snapshot the two JSON channels independently so caller membership
        # changes cannot modify the frozen document after construction.
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
        raise TypeError(f"MessageDocument {field_name} must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"MessageDocument {field_name} keys must be strings.")

    # Preserve values exactly and leave recursive JSON/number policy to the
    # document validator while detaching top-level membership from the caller.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)
