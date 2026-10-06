"""Open structural contract for items in a message entry content list."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.message_content_kind import MessageContentKind


@runtime_checkable
class MessageContent(Protocol):
    """Describe one independently mapped message content item.

    Content belongs to a message entry's ordered content collection and is not a
    MessageElement tree node. Implementations remain structural so providers can
    add content kinds without inheritance or registration. Concrete content types
    own their payload fields; this protocol defines only shared identity and data.
    """

    @property
    def id(self) -> str:
        """Return the stable identifier local to the enclosing message document."""
        # Preserve the producer's identity without deriving it from position or
        # kind; document-level validation owns uniqueness and reference rules.
        ...

    @property
    def kind(self) -> MessageContentKind:
        """Return the open kind describing this content representation."""
        # The open kind selects a concrete content interpretation without making
        # this shared protocol depend on text, JSON, Artifact, or unknown payloads.
        ...

    @property
    def metadata(self) -> Extensions:
        """Return non-control JSON metadata describing this content item."""
        # Metadata remains descriptive and cannot move the content into the
        # element tree, alter entry ordering, or substitute for payload fields.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned content fields for forward compatibility."""
        # Older consumers keep provider fields observable without interpreting
        # them as element children, task parameters, or mapping instructions.
        ...
