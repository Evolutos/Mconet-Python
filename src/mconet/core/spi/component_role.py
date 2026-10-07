"""Open role identifiers for uniquely selected runtime components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier, validate_open_identifier


@dataclass(frozen=True, slots=True)
class ComponentRole:
    """Represent a standard or future execution-chain component role.

    Roles identify positions in an execution plan and selection snapshot; they
    are not component IDs or caller configuration keys. A validated open
    identifier preserves future roles without changing this value type.
    """

    id: OpenIdentifier
    """Validated open identifier naming one execution-chain role."""

    def __post_init__(self) -> None:
        """Require the nominal identifier type and portable open syntax."""
        identifier = cast(object, self.id)
        # Reject primitive substitutes before validation so every standard and
        # extension role uses the common immutable identifier representation.
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError("ComponentRole id must be an OpenIdentifier.")

        # Validate portability without comparing against the current standard
        # role list; newer runtimes can introduce roles losslessly.
        validate_open_identifier(identifier)

    def __str__(self) -> str:
        """Return the exact preserved component role identifier text."""
        # Explicit conversion exposes role identity only and never derives a
        # component instance, configuration field, or selection priority.
        return self.id.value
