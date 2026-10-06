"""Open structural contract for nodes in a message document tree."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_element_value import MessageElementValue
from mconet.core.domain.message_relation import MessageRelation


@runtime_checkable
class MessageElement(Protocol):
    """Describe one message-domain tree node without coupling it to task nodes.

    Implementations remain structural so integrations can add message-specific
    element kinds without registration or inheritance from an SDK base class.
    This protocol exposes data only; tree consistency, kind composition, ID
    uniqueness, and relation resolution belong to later validators.
    """

    @property
    def id(self) -> str:
        """Return the stable identifier local to the enclosing message document."""
        # Preserve producer identity exactly; uniqueness and non-empty rules need
        # the complete document and therefore cannot be decided by this protocol.
        ...

    @property
    def kind(self) -> MessageElementKind:
        """Return the open kind describing this element's message semantics."""
        # Expose the kind contract without switching on known identifiers so a
        # custom element remains representable by older SDK implementations.
        ...

    @property
    def name(self) -> str | None:
        """Return an optional producer-supplied element name."""
        # None means no name was supplied; this field is descriptive and never
        # substitutes for the stable document-local element identifier.
        ...

    @property
    def attributes(self) -> Extensions:
        """Return element-specific JSON attributes used by its kind semantics."""
        # Attributes remain separate from the direct value and descriptive
        # metadata so consumers can interpret each channel intentionally.
        ...

    @property
    def value(self) -> MessageElementValue | None:
        """Return an optional direct JSON value carried by this element."""
        # Generic inline data stays within MessageElementValue; specialized
        # message payloads belong to concrete element or content fields.
        ...

    @property
    def sub_elements(self) -> Sequence[MessageElement]:
        """Return child elements in stable document order."""
        # Read-only sequence access preserves ordering while allowing custom
        # implementations to choose their own immutable or mutable storage.
        ...

    @property
    def relations(self) -> Sequence[MessageRelation]:
        """Return directed element relations in stable declaration order."""
        # Relations remain unresolved references here; only a document-level
        # validator has the complete element index needed to check endpoints.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return non-control JSON metadata describing this element."""
        # Metadata is observational data and must not alter kind selection,
        # child traversal, relation direction, or task execution behavior.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned element fields for forward compatibility."""
        # Keeping extensions observable without interpreting them lets newer
        # producers add fields while older consumers preserve the full element.
        ...
