"""Client component injection precedes the binding layer."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.runtime._single_component_selection import select_required_component
from mconet.core.spi import ComponentDescriptor, ComponentRole, RuntimeComponent


class _Component:
    """Named component used only to observe which layer wins."""

    def __init__(self, name: str) -> None:
        """Store metadata whose name identifies the source layer."""
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application")


def test_client_component_precedes_binding() -> None:
    """Verify a client instance is chosen when the interaction layer is empty."""
    client = _Component("client")
    binding = _Component("binding")
    sdk = _Component("sdk")
    selected = select_required_component(
        ComponentRole(OpenIdentifier("transport.unary")),
        (
            (),
            (cast(RuntimeComponent, client),),
            (cast(RuntimeComponent, binding),),
            (cast(RuntimeComponent, sdk),),
        ),
        lambda _component: True,
    )

    assert selected.component is client
