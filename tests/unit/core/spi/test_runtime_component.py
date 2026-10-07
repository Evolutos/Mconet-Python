"""Structural conformance tests for the runtime component protocol."""

from dataclasses import dataclass

from mconet.core.spi import ComponentDescriptor, RuntimeComponent


@dataclass(frozen=True, slots=True)
class _ApplicationComponent:
    """Application component exposing only the required descriptor field."""

    descriptor: ComponentDescriptor
    """Static metadata consumed by Core component resolution."""


class _PropertyComponent:
    """Custom component that exposes metadata through a read-only property."""

    def __init__(self, descriptor: ComponentDescriptor) -> None:
        """Store descriptor metadata behind the public protocol property."""
        # Private storage proves the protocol does not depend on a dataclass field
        # or a specific concrete component representation.
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact descriptor supplied during construction."""
        # No copy or wrapper is required because ComponentDescriptor is already
        # an immutable value object shared safely across component consumers.
        return self._descriptor


@dataclass(frozen=True, slots=True)
class _UndescribedComponent:
    """Component-shaped object intentionally lacking static metadata."""

    label: str
    """Unrelated field that cannot substitute for a descriptor."""


def _read_descriptor(component: RuntimeComponent) -> ComponentDescriptor:
    """Return metadata through the statically typed structural boundary."""
    # Accepting an application-defined value here proves callers need no SDK
    # base class, adapter, cast, or registry lookup to consume its descriptor.
    return component.descriptor


def test_runtime_component_accepts_descriptor_only_custom_component() -> None:
    """Verify one descriptor field satisfies the complete component protocol."""
    descriptor = ComponentDescriptor("Application Codec", "1", "application")
    component = _ApplicationComponent(descriptor)

    # Structural recognition and typed consumption both retain the custom
    # component and exact descriptor without inheritance or registration.
    assert isinstance(component, RuntimeComponent)
    assert _read_descriptor(component) is descriptor
    assert not hasattr(component, "component_id")
    assert not hasattr(component, "close")


def test_runtime_component_accepts_read_only_descriptor_property() -> None:
    """Verify protocol conformance is independent of concrete storage style."""
    descriptor = ComponentDescriptor("Plugin Resolver", "2", "plugin")
    component = _PropertyComponent(descriptor)

    # A property implements the documented read-only surface while private
    # storage stays entirely owned by the custom component.
    assert isinstance(component, RuntimeComponent)
    assert component.descriptor is descriptor


def test_runtime_component_rejects_object_without_descriptor() -> None:
    """Verify unrelated component-like data cannot satisfy the protocol."""
    component = _UndescribedComponent("missing metadata")

    # Runtime structural recognition checks the required surface only; no name,
    # label, behavior method, or inheritance marker can replace descriptor.
    assert not isinstance(component, RuntimeComponent)
