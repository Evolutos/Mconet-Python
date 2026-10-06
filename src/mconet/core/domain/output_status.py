"""Open result status values for parsed and assembled model output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)


@dataclass(frozen=True, slots=True)
class OutputStatus:
    """Represent a portable standard or extension output status.

    A validated open identifier keeps documented statuses stable while allowing
    a newer service or task integration to preserve future states exactly. This
    value records status identity only; stop reason, diagnostics, protocol state,
    task result, cancellation, and error details remain separate output fields.
    """

    id: OpenIdentifier
    """The validated open identifier naming the output status."""

    def __post_init__(self) -> None:
        """Require the nominal identifier type and portable identifier syntax."""
        identifier = cast(object, self.id)
        # Validate storage nominally before syntax so dynamic callers cannot use
        # a bare string as an alternate status representation.
        if not isinstance(identifier, OpenIdentifier):
            raise TypeError("OutputStatus id must be an OpenIdentifier.")

        # Reuse the common open grammar without comparing against known values;
        # future statuses remain lossless instead of collapsing to ``unknown``.
        validate_open_identifier(identifier)

    def __str__(self) -> str:
        """Return the exact preserved output status identifier text."""
        # String conversion is explicit and non-normalizing so standard and
        # extension values have identical stable wire representations.
        return self.id.value
