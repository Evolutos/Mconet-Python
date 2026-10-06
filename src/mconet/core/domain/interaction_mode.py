"""Open structural contract for interaction execution mode identity."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class InteractionMode(Protocol):
    """Identify how one model interaction is executed.

    The contract remains open so standard and future execution modes use the
    same read-only shape without an SDK enum, base class, or registry. A mode
    names execution behavior only; task identity, support policy, lifecycle,
    transport selection, and public client entry points remain separate concerns.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this execution mode."""
        # Structural conformance preserves identity but does not imply that the
        # current runtime or selected task can execute the represented mode.
        ...
