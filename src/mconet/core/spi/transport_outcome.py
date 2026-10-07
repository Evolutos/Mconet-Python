"""Open normalized outcomes reported by transport implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier, validate_open_identifier


@dataclass(frozen=True, slots=True)
class TransportOutcome:
    """Represent a standard or future normalized transport result.

    Standard outcomes are ``success``, ``service_error``, and
    ``transport_error``. A validated open identifier lets a future transport
    preserve a more specific portable result without changing this value type.
    Native status, response headers, media type, and body remain separate facts.
    """

    id: OpenIdentifier
    """Validated open identifier naming the normalized transport outcome."""

    def __post_init__(self) -> None:
        """Require the nominal identifier type and portable identifier syntax."""
        identifier = cast(object, self.id)
        # Reject primitive substitutes before validating syntax so every outcome
        # follows the same immutable OpenIdentifier representation.
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError("TransportOutcome id must be an OpenIdentifier.")

        # Validate portability without comparing against a closed value set;
        # future normalized outcomes remain exact and distinguishable.
        validate_open_identifier(identifier)

    def __str__(self) -> str:
        """Return the exact preserved transport outcome identifier text."""
        # Explicit conversion never maps unknown outcomes onto a standard value
        # and does not infer a result from an HTTP or RPC status code.
        return self.id.value
