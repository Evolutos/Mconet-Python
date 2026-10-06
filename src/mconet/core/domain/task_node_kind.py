"""Open structural contract for task node classifications."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class TaskNodeKind(Protocol):
    """Classify a task node without closing future kind identifiers.

    Identity and tree composition remain independent facts. Custom task nodes can
    therefore introduce a new identifier while still declaring whether they are
    leaves or containers, without inheriting an SDK base class or modifying a
    central enumeration.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this task node kind."""
        # Standard and provider-defined kinds share one identity boundary; the
        # contract does not infer composition from identifier text.
        ...

    @property
    def composition(self) -> Literal["leaf", "container"]:
        """Return whether nodes of this kind may contain child nodes."""
        # The two structural modes define traversal behavior; node validators
        # later enforce that actual children agree with the declared mode.
        ...
