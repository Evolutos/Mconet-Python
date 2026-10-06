"""Open phase identifiers for interaction diagnostics and failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)


@dataclass(frozen=True, slots=True)
class InteractionPhase:
    """Represent a portable standard or extension interaction phase.

    A validated open identifier allows runtime and integration implementations
    to report future phases without forcing older SDKs to replace their exact
    value with a generic fallback.
    """

    id: OpenIdentifier
    """The validated open identifier for this phase."""

    def __post_init__(self) -> None:
        """Require the nominal identifier type and its portable syntax."""
        identifier = cast(object, self.id)
        # Validate syntax without comparing against a closed list so phases from
        # newer runtimes remain representable and lossless.
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError("InteractionPhase id must be an OpenIdentifier.")
        validate_open_identifier(identifier)

    def __str__(self) -> str:
        """Return the preserved phase identifier text."""
        return self.id.value
