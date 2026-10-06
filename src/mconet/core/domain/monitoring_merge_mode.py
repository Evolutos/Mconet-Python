"""Open modes for combining client and interaction monitors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)


@dataclass(frozen=True, slots=True)
class MonitoringMergeMode:
    """Name a standard or future monitor-list merge strategy.

    Standard modes are ``append``, ``prepend``, and ``replace``. The identifier
    remains open so later SDK versions can preserve a new strategy without
    coercing it to a known mode or an unknown sentinel. This value object names
    the strategy only; monitoring configuration owns default selection and list
    merging behavior.
    """

    mode: OpenIdentifier
    """The validated open identifier naming the monitor merge strategy."""

    def __post_init__(self) -> None:
        """Require a nominal portable identifier without closing the mode set."""
        mode = cast(object, self.mode)
        # Reuse the shared identifier grammar without comparing against the three
        # current modes, which keeps future strategies exact and distinguishable.
        if not isinstance(mode, OpenIdentifier):
            raise TypeError("MonitoringMergeMode mode must be an OpenIdentifier.")
        validate_open_identifier(mode)

    def __str__(self) -> str:
        """Return the exact merge mode identifier text."""
        # String conversion preserves both standard and unknown values without
        # performing default selection or monitor-list manipulation.
        return self.mode.value
