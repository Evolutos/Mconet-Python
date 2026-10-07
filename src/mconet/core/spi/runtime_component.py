"""Structural metadata boundary shared by injectable runtime components."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.spi.component_descriptor import ComponentDescriptor


@runtime_checkable
class RuntimeComponent(Protocol):
    """Expose static component metadata without requiring SDK inheritance.

    Concrete adapters, codecs, transports, resolvers, handlers, monitors, and
    factories combine this minimal protocol with their own behavior contracts.
    The boundary deliberately defines no registry identity, execution method,
    mutable state, ownership, or lifecycle operation. Resource-owning components
    opt into the separate ``CloseableRuntimeComponent`` refinement; stateless
    components remain valid without a no-op close method.
    """

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the immutable type, capability, and provenance metadata."""
        # A read-only property lets both stored attributes and computed accessors
        # satisfy the protocol while preventing Core from replacing metadata.
        ...
