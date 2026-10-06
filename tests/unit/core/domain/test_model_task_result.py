"""Structural openness and ownership tests for ModelTaskResult."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    ModelTaskResult,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide the standard root Kind for result document fixtures."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Container composition retained for later semantic validation."""


@dataclass(frozen=True, slots=True)
class _ResultDescriptor:
    """Provide one application-owned task result descriptor."""

    type: OpenIdentifier
    """Open task result identity."""

    version: str | None
    """Optional task result contract version."""

    input_schema_id: str | None
    """Optional input schema identity retained by the shared descriptor shape."""

    output_schema_id: str | None
    """Optional result document schema identity."""

    metadata: Extensions
    """Portable descriptor metadata."""

    extensions: Extensions
    """Unknown descriptor fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _CustomModelTaskResult:
    """Provide a complete application-owned ModelTaskResult implementation."""

    descriptor: TaskDescriptor
    """Task result identity and schema contract."""

    document: TaskDocument
    """Versioned task result tree."""

    artifacts: ArtifactCatalog
    """Artifact reference scope owned only by this result."""

    metadata: Extensions
    """Portable result-level descriptive data."""

    extensions: Extensions
    """Unknown result fields retained for forward compatibility."""


def _descriptor(task_type: str = "vendor.document_compare") -> TaskDescriptor:
    """Create one complete open descriptor for result protocol fixtures."""
    # A custom structural implementation proves result extensibility does not
    # depend on an SDK-provided concrete task descriptor class.
    return _ResultDescriptor(
        type=OpenIdentifier(task_type),
        version="2026.10",
        input_schema_id="schema.vendor.input",
        output_schema_id="schema.vendor.result",
        metadata=MappingProxyType({"owner": "integration"}),
        extensions=MappingProxyType({"vendor.descriptor": True}),
    )


def _document() -> TaskDocument:
    """Create one concrete versioned result document with an empty root."""
    # The structural root Kind remains application-owned while TaskDocument gives
    # every result one complete versioned tree rather than a loose node sequence.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.result_root"), "container")
    return TaskDocument("1.0", TaskGroupNode("result-root", kind, ()))


def _accept_model_task_result(result: ModelTaskResult) -> ModelTaskResult:
    """Return one result after crossing the static protocol boundary."""
    # Pyright verifies complete property types at the caller, complementing the
    # runtime Protocol check that verifies all required attributes are present.
    return result


def test_model_task_result_accepts_custom_structural_implementation() -> None:
    """Verify applications can define new result families without SDK inheritance."""
    descriptor = _descriptor()
    document = _document()
    artifacts = ArtifactCatalog()
    metadata: Extensions = MappingProxyType({"latencyClass": "interactive"})
    extensions: Extensions = MappingProxyType({"vendor.confidence": 0.97})
    result = _CustomModelTaskResult(
        descriptor,
        document,
        artifacts,
        metadata,
        extensions,
    )

    # Runtime recognition and exact object identities prove the open protocol
    # neither registers concrete types nor merges independently owned fields.
    assert isinstance(result, ModelTaskResult)
    assert _accept_model_task_result(result) is result
    assert result.descriptor is descriptor
    assert result.document is document
    assert result.artifacts is artifacts
    assert result.metadata is metadata
    assert result.extensions is extensions


def test_model_task_result_owns_an_independent_artifact_catalog() -> None:
    """Verify result references cannot fall back to a request or external scope."""
    result_catalog = ArtifactCatalog()
    unrelated_request_catalog = ArtifactCatalog()
    result = _CustomModelTaskResult(
        _descriptor("conversation.generate"),
        _document(),
        result_catalog,
        MappingProxyType({}),
        MappingProxyType({}),
    )

    # A concrete empty catalog means this result has no artifacts; its identity is
    # distinct from another empty scope and cannot trigger implicit lookup there.
    assert result.artifacts is result_catalog
    assert result.artifacts is not unrelated_request_catalog
    assert result.artifacts.artifacts == ()
    assert result.metadata == {}
    assert result.extensions == {}


def test_model_task_result_exposes_only_task_result_owned_fields() -> None:
    """Verify enclosing output and task-specific projections remain external."""
    properties = {
        name
        for name, value in vars(ModelTaskResult).items()
        if isinstance(value, property)
    }

    # The exact five-property surface separates authoritative task result data
    # from parsed-response facts, Runtime diagnostics, and convenience views.
    assert properties == {
        "descriptor",
        "document",
        "artifacts",
        "metadata",
        "extensions",
    }
    for field_name in (
        "target",
        "resolved_model",
        "status",
        "stop_reason",
        "usage",
        "diagnostics",
        "protocol_state",
        "messages",
        "text",
        "transport",
    ):
        assert field_name not in properties


def test_model_task_result_requires_the_complete_field_surface() -> None:
    """Verify descriptor and document alone cannot masquerade as a task result."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteResult:
        """Intentionally omit artifacts, metadata, and extension properties."""

        descriptor: TaskDescriptor
        """Task identity exposed by the incomplete result fixture."""

        document: TaskDocument
        """Result tree exposed without its required sibling boundaries."""

    result = _IncompleteResult(_descriptor(), _document())

    # Empty fields still require explicit values, so absence cannot conflate an
    # empty result scope with an unresolved or partially decoded result.
    assert not isinstance(result, ModelTaskResult)
