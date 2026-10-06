"""Open error categories for normalized interaction failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)


@dataclass(frozen=True, slots=True)
class ErrorCategory:
    """Represent a portable standard or extension error category.

    The category uses a validated :class:`OpenIdentifier` rather than a closed
    enum. Standard categories therefore have stable values while categories
    introduced by a future SDK or integration remain lossless.
    """

    id: OpenIdentifier
    """The validated open identifier for this category."""

    def __post_init__(self) -> None:
        """Require the nominal identifier type and its portable syntax."""
        identifier = cast(object, self.id)
        # Keep category openness in OpenIdentifier while requiring every stored
        # category to satisfy the same portable wire grammar.
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError("ErrorCategory id must be an OpenIdentifier.")
        validate_open_identifier(identifier)

    def __str__(self) -> str:
        """Return the preserved category identifier text."""
        return self.id.value
