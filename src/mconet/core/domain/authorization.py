"""Opaque runtime authorization contract for model service access."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class Authorization(Protocol):
    """Describe an authorization mechanism without exposing its credentials.

    Implementations own their authentication data and may add arbitrary runtime
    fields. Core components preserve this object opaquely until a compatible
    authorization handler applies it; the contract is not a payload model and
    must not be serialized through ordinary payload schemas or encoders.
    """

    @property
    def kind(self) -> OpenIdentifier:
        """Return the open identifier used to select a compatible handler."""
        # The protocol exposes identity only. Concrete handlers, rather than the
        # domain contract, interpret any credentials held by an implementation.
        ...
