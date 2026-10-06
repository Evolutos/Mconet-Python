"""Open structural contract for message content kind identity."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class MessageContentKind(Protocol):
    """Identify a standard or provider-defined message content representation.

    The protocol remains separate from MessageElementKind because content items
    belong to an entry's ordered content list rather than the message element
    tree. Custom content can introduce an open identifier without inheriting an
    SDK base class or modifying a central enumeration.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this content kind."""
        # Identity alone selects content representation. Concrete MessageContent
        # implementations own their payload, metadata, and extension fields.
        ...
