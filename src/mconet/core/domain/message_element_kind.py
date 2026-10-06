"""Open structural contract for message element classifications."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class MessageElementKind(Protocol):
    """Classify a message element without closing future kind identifiers.

    Identity, category, and tree composition remain independent facts. Custom
    message elements can therefore introduce a new identifier and category while
    still declaring whether they are leaves or containers, without inheriting an
    SDK base class or modifying a central enumeration.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this element kind."""
        # Standard and provider-defined kinds share one identity boundary; the
        # contract does not infer category or composition from identifier text.
        ...

    @property
    def category(self) -> str:
        """Return the producer-defined classification category."""
        # Category stays open text so future semantic groupings do not require a
        # Core enum change or collapse into a generic unknown category.
        ...

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return whether elements of this kind may contain sub-elements."""
        # The two structural modes define traversal behavior; element validators
        # later enforce that actual children agree with the declared mode.
        ...
