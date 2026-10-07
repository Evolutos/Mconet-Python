"""Immutable criteria used to resolve one transport component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier


@dataclass(frozen=True, slots=True)
class TransportSelection:
    """Describe an optional transport kind and required capabilities.

    The open kind and capability identifiers constrain component resolution
    without naming a component or describing its static metadata. An immutable
    set gives requirements order-independent membership and value semantics.
    """

    transport_kind: OpenIdentifier | None = None
    """Optional open identifier for the protocol plan's transport family."""

    required_capabilities: frozenset[OpenIdentifier] = frozenset()
    """Immutable set of capabilities every compatible transport must declare."""

    def __post_init__(self) -> None:
        """Require optional nominal kind and immutable capability identifiers."""
        transport_kind = cast(object, self.transport_kind)
        required_capabilities = cast(object, self.required_capabilities)

        # Keep transport kinds open for future protocols while preventing a raw
        # string from bypassing the shared identifier value contract.
        if transport_kind is not None and not isinstance(
            transport_kind, OpenIdentifier
        ):
            raise TypeError(
                "TransportSelection transport_kind must be an OpenIdentifier or None."
            )

        # Frozenset matches language-neutral Set semantics: membership is unique,
        # order-independent, hashable, and cannot change during resolution.
        if not isinstance(required_capabilities, frozenset):
            raise TypeError(
                "TransportSelection required_capabilities must be a frozenset."
            )
        for capability in cast(frozenset[object], required_capabilities):
            if not isinstance(capability, OpenIdentifier):
                raise TypeError(
                    "TransportSelection required_capabilities must contain "
                    "OpenIdentifier values."
                )
