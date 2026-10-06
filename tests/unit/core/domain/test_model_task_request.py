"""Structural openness and boundary tests for ModelTaskRequest."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    ModelTaskRequest,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide the standard root Kind for task document fixtures."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Container composition retained for later semantic validation."""


@dataclass(frozen=True, slots=True)
class _CustomTaskDescriptor:
    """Provide one application-owned TaskDescriptor implementation."""

    type: OpenIdentifier
    """Open task identity."""

    version: str | None
    """Optional task contract version."""

    input_schema_id: str | None
    """Optional input schema identity."""

    output_schema_id: str | None
    """Optional output schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _CustomModelTaskRequest:
    """Provide a complete application-owned ModelTaskRequest implementation."""

    descriptor: TaskDescriptor
    """Task identity and schema contract."""

    document: TaskDocument
    """Versioned task input and configuration tree."""

    artifacts: ArtifactCatalog
    """Artifact reference scope owned by this request only."""

    metadata: Extensions
    """Portable request-level descriptive data."""

    extensions: Extensions
    """Unknown request fields retained for forward compatibility."""


def _descriptor(task_type: str = "vendor.document_compare") -> TaskDescriptor:
    """Create one complete open descriptor for protocol fixtures."""
    # A custom structural implementation proves request extensibility does not
    # depend on an SDK-provided concrete task descriptor class.
    return _CustomTaskDescriptor(
        type=OpenIdentifier(task_type),
        version="2026.10",
        input_schema_id="schema.vendor.input",
        output_schema_id="schema.vendor.output",
        metadata=MappingProxyType({"owner": "application"}),
        extensions=MappingProxyType({"vendor.option": True}),
    )


def _document() -> TaskDocument:
    """Create one concrete versioned task document with an empty root."""
    # The root Kind is represented structurally while TaskDocument retains the
    # concrete immutable root required by the common task boundary.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    return TaskDocument("1.0", TaskGroupNode("root", kind, ()))


def _accept_model_task_request(request: ModelTaskRequest) -> ModelTaskRequest:
    """Return one request after crossing the static protocol boundary."""
    # Pyright checks the caller's complete property types here, complementing the
    # runtime protocol check that verifies required attribute presence.
    return request


def test_model_task_request_accepts_custom_structural_implementation() -> None:
    """Verify applications can define new tasks without SDK inheritance."""
    descriptor = _descriptor()
    document = _document()
    artifacts = ArtifactCatalog()
    metadata: Extensions = MappingProxyType({"traceLabel": "comparison"})
    extensions: Extensions = MappingProxyType({"vendor.priority": 2})
    request = _CustomModelTaskRequest(
        descriptor,
        document,
        artifacts,
        metadata,
        extensions,
    )

    # Runtime structural recognition proves registration is unnecessary; exact
    # object identity proves the protocol does not merge or derive its fields.
    assert isinstance(request, ModelTaskRequest)
    assert _accept_model_task_request(request) is request
    assert request.descriptor is descriptor
    assert request.document is document
    assert request.artifacts is artifacts
    assert request.metadata is metadata
    assert request.extensions is extensions


def test_model_task_request_keeps_document_and_artifact_scope_independent() -> None:
    """Verify no-artifact requests still carry a concrete empty local catalog."""
    document = _document()
    artifacts = ArtifactCatalog()
    request = _CustomModelTaskRequest(
        _descriptor("conversation.generate"),
        document,
        artifacts,
        MappingProxyType({}),
        MappingProxyType({}),
    )

    # Empty catalog is a real resolved scope rather than None. Its membership is
    # not inferred from the TaskDocument or either request preservation channel.
    assert request.document is document
    assert request.artifacts is artifacts
    assert request.artifacts.artifacts == ()
    assert request.metadata == {}
    assert request.extensions == {}


def test_model_task_request_exposes_only_task_owned_fields() -> None:
    """Verify outer interaction and message fields are absent from the protocol."""
    properties = {
        name
        for name, value in vars(ModelTaskRequest).items()
        if isinstance(value, property)
    }

    # The exact surface separates the five owned values. Message input belongs in
    # concrete nodes, while target, access, credentials, and transport stay outer.
    assert properties == {
        "descriptor",
        "document",
        "artifacts",
        "metadata",
        "extensions",
    }
    for field_name in (
        "messages",
        "target",
        "service_access",
        "authorization",
        "endpoint",
        "transport",
        "protocol_payload",
    ):
        assert field_name not in properties


def test_model_task_request_requires_the_complete_field_surface() -> None:
    """Verify descriptor and document alone cannot masquerade as the protocol."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteRequest:
        """Intentionally omit artifacts, metadata, and extensions."""

        descriptor: TaskDescriptor
        """Task identity exposed by the incomplete fixture."""

        document: TaskDocument
        """Task tree exposed without its required sibling boundaries."""

    request = _IncompleteRequest(_descriptor(), _document())

    # Empty fields still require explicit values, so absence cannot conflate no
    # artifacts or metadata with an unresolved or partially decoded request.
    assert not isinstance(request, ModelTaskRequest)
