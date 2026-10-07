"""Open ownership identities for runtime component resource lifecycles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier, validate_open_identifier


@dataclass(frozen=True, slots=True)
class ComponentOwnership:
    """Name the current owner of one runtime component's resource lifecycle.

    Standard ownership identities are ``builtin`` for a component created and
    owned by the SDK and ``application`` for a component directly supplied and
    retained by application code. The identifier remains open so a later SDK or
    language-specific convenience layer can preserve an explicit transferred or
    shared ownership model without changing this value representation.

    Ownership is independent from :class:`ComponentDescriptor` provenance. A
    plugin component can be created by the SDK or injected by an application,
    so descriptor source must never be reinterpreted as lifecycle authority.
    This value records identity only; ownership determination, component
    association, close capability, close ordering, and idempotent release belong
    to later runtime steps.
    """

    id: OpenIdentifier
    """Validated open identifier naming the component lifecycle owner."""

    def __post_init__(self) -> None:
        """Require nominal immutable storage and portable open syntax."""
        identifier = cast(object, self.id)

        # Reject bare strings and identifier-shaped objects so every standard and
        # extension value uses the same immutable OpenIdentifier representation.
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError("ComponentOwnership id must be an OpenIdentifier.")

        # Apply only portable syntax rules. Do not compare with the two current
        # standard values, which would close the extension point prematurely.
        validate_open_identifier(identifier)

    def __str__(self) -> str:
        """Return the exact preserved ownership identifier text."""
        # Explicit conversion neither maps unknown values to a default nor infers
        # ownership from a component descriptor or injection source.
        return self.id.value
