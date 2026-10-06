"""Structural openness tests for the ModelDescriptor protocol."""

from dataclasses import dataclass
from types import MappingProxyType

from mconet.core.domain import Extensions, ModelDescriptor, OpenIdentifier


@dataclass(frozen=True, slots=True)
class _CustomModelDescriptor:
    """Test implementation proving the protocol requires no SDK base class."""

    name: str
    display_name: str | None
    family: OpenIdentifier | None
    version: str | None
    description: str | None
    metadata: Extensions
    extensions: Extensions


def test_model_descriptor_accepts_custom_structural_implementation() -> None:
    """Verify callers can provide a complete descriptor without registration."""
    descriptor = _CustomModelDescriptor(
        name="provider-model-1",
        display_name="Provider Model",
        family=OpenIdentifier("vendor.future_family"),
        version="2026-10",
        description="Custom model description",
        metadata=MappingProxyType({"contextWindow": 128_000}),
        extensions=MappingProxyType({"futureField": {"enabled": True}}),
    )

    # Runtime structural recognition verifies the full property surface while
    # retaining the custom concrete type and its exact extension data.
    assert isinstance(descriptor, ModelDescriptor)
    assert descriptor.name == "provider-model-1"
    assert descriptor.metadata == {"contextWindow": 128_000}
    assert descriptor.extensions == {"futureField": {"enabled": True}}
    assert descriptor.family == OpenIdentifier("vendor.future_family")


def test_model_descriptor_requires_complete_field_surface() -> None:
    """Verify a name alone cannot masquerade as the complete public protocol."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteDescriptor:
        """Intentionally omit optional and extension properties."""

        name: str

    # Optional values may be None, but the properties themselves are required
    # so every consumer sees one stable descriptor shape.
    assert not isinstance(_IncompleteDescriptor("model"), ModelDescriptor)
