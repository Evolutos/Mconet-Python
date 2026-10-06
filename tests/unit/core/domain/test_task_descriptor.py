"""Structural openness tests for the TaskDescriptor protocol."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from mconet.core.domain import Extensions, OpenIdentifier, TaskDescriptor


@dataclass(frozen=True, slots=True)
class _CustomTaskDescriptor:
    """Provide a complete application-owned TaskDescriptor implementation."""

    type: OpenIdentifier
    """Open task identity supplied without a known-type registry."""

    version: str | None
    """Optional task contract version."""

    input_schema_id: str | None
    """Optional input schema identity independent from task type."""

    output_schema_id: str | None
    """Optional output schema identity independent from input schema."""

    metadata: Extensions
    """Portable non-control facts associated with the task."""

    extensions: Extensions
    """Unknown portable fields retained for forward compatibility."""


def _accept_task_descriptor(descriptor: TaskDescriptor) -> TaskDescriptor:
    """Return one descriptor after crossing the static protocol boundary."""
    # Pyright checks the caller's complete property types here, complementing
    # runtime-checkable Protocol recognition that verifies attribute presence.
    return descriptor


def test_task_descriptor_accepts_custom_structural_implementation() -> None:
    """Verify applications can define tasks without an SDK base class."""
    descriptor = _CustomTaskDescriptor(
        type=OpenIdentifier("vendor.document_compare"),
        version="2026.10",
        input_schema_id="schema.vendor.document_pair",
        output_schema_id="schema.vendor.comparison_result",
        metadata=MappingProxyType({"language": "zh-CN"}),
        extensions=MappingProxyType({"vendor.options": {"explainDifferences": True}}),
    )

    # Runtime structural recognition proves no registration or inheritance is
    # required; the helper additionally proves static structural compatibility.
    assert isinstance(descriptor, TaskDescriptor)
    assert _accept_task_descriptor(descriptor) is descriptor
    assert descriptor.type == OpenIdentifier("vendor.document_compare")
    assert descriptor.version == "2026.10"
    assert descriptor.input_schema_id == "schema.vendor.document_pair"
    assert descriptor.output_schema_id == "schema.vendor.comparison_result"
    assert descriptor.metadata == {"language": "zh-CN"}
    assert descriptor.extensions == {"vendor.options": {"explainDifferences": True}}


def test_task_descriptor_preserves_independent_optional_absence() -> None:
    """Verify version and both schema identities may be absent independently."""
    descriptor = _CustomTaskDescriptor(
        type=OpenIdentifier("conversation.generate"),
        version=None,
        input_schema_id=None,
        output_schema_id=None,
        metadata=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )

    # None represents explicit absence for each optional contract dimension;
    # the protocol does not infer schema IDs or a version from the task type.
    assert isinstance(descriptor, TaskDescriptor)
    assert descriptor.version is None
    assert descriptor.input_schema_id is None
    assert descriptor.output_schema_id is None
    assert descriptor.metadata == {}
    assert descriptor.extensions == {}


def test_task_descriptor_requires_the_complete_field_surface() -> None:
    """Verify a task type alone cannot masquerade as the complete protocol."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteTaskDescriptor:
        """Intentionally omit version, schemas, metadata, and extensions."""

        type: OpenIdentifier
        """Only the task identity is present."""

    descriptor = _IncompleteTaskDescriptor(OpenIdentifier("conversation.generate"))

    # Optional fields may contain None, but the properties themselves remain
    # mandatory so all consumers observe one stable structural surface.
    assert not isinstance(descriptor, TaskDescriptor)
