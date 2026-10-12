"""Binding component injection precedes the SDK default layer."""

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


def test_binding_component_precedes_sdk_default() -> None:
    """Verify a binding instance is chosen when higher layers are empty."""
    binding = _Component("binding")
    sdk = _Component("sdk")
    selected = select_required_component(
        ComponentRole(OpenIdentifier("codec.request.encoder")),
        (
            (),
            (),
            (cast(RuntimeComponent, binding),),
            (cast(RuntimeComponent, sdk),),
        ),
        lambda _component: True,
    )

    assert selected.component is binding
