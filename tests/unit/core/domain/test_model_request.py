"""Structural openness and ownership tests for ModelRequest."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    UriValue,
)


@dataclass(frozen=True, slots=True)
class _TaskKind:
    """Provide the container Kind used by the task document fixture."""

    id: OpenIdentifier
    """Open task node Kind identifier."""

    composition: Literal["leaf", "container"]
    """Container composition retained for later semantic validation."""


@dataclass(frozen=True, slots=True)
class _TaskDescriptor:
    """Provide an application-owned task descriptor for request fixtures."""

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
class _TaskRequest:
    """Provide an application-owned model task request implementation."""

    descriptor: TaskDescriptor
    """Open task identity and schema contract."""

    document: TaskDocument
    """Versioned task input and control tree."""

    artifacts: ArtifactCatalog
    """Artifact reference scope owned by the task request."""

    metadata: Extensions
    """Portable task metadata."""

    extensions: Extensions
    """Unknown task fields retained for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Provide an application-owned model target implementation."""

    service_id: OpenIdentifier
    """Selected model service identity."""

    protocol_id: OpenIdentifier
    """Selected interaction protocol identity."""

    model: NamedModel
    """Selected provider-facing model descriptor."""

    deployment_id: str | None
    """Optional service-side deployment identity."""

    extensions: Extensions
    """Unknown target fields retained for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Provide an application-owned authorization implementation."""

    kind: OpenIdentifier
    """Open authorization mechanism identity."""


@dataclass(frozen=True, slots=True)
class _ServiceAccess:
    """Provide complete unresolved per-request service access input."""

    endpoint: UriValue | None
    """Optional service endpoint."""

    authorization: Authorization | None
    """Optional unresolved authorization input."""

    headers: Headers
    """Ordered non-sensitive custom headers."""

    query: QueryParameters
    """Ordered non-sensitive custom query parameters."""

    api_version: str | None
    """Optional provider API version."""

    project_id: str | None
    """Optional provider project identity."""

    tenant_id: str | None
    """Optional provider tenant identity."""

    extensions: Extensions
    """Unknown access fields retained for forward compatibility."""


@dataclass(frozen=True, slots=True)
class _CustomModelRequest:
    """Provide a complete application-owned ModelRequest implementation."""

    target: ModelTarget
    """Independent model interaction target."""

    task: ModelTaskRequest
    """Independent open task request."""

    service_access: ServiceAccess | None
    """Optional unresolved access override for this request."""

    metadata: Extensions
    """Portable request-level descriptive data."""

    extensions: Extensions
    """Unknown request fields retained for forward compatibility."""


def _target() -> ModelTarget:
    """Create one structurally complete model target fixture."""
    # Use distinct service and protocol identifiers to prove the outer request
    # retains target selection rather than deriving either value from the model.
    return _Target(
        service_id=OpenIdentifier("service.vendor"),
        protocol_id=OpenIdentifier("protocol.vendor"),
        model=NamedModel("vendor-model"),
        deployment_id="primary",
        extensions=MappingProxyType({"routingHint": "east"}),
    )


def _task() -> ModelTaskRequest:
    """Create one structurally complete custom task request fixture."""
    # A non-conversation task demonstrates that the outer envelope remains open
    # and does not elevate message or generation fields into its own contract.
    kind: TaskNodeKind = _TaskKind(OpenIdentifier("task.root"), "container")
    descriptor: TaskDescriptor = _TaskDescriptor(
        type=OpenIdentifier("vendor.document_compare"),
        version="2026.10",
        input_schema_id="schema.vendor.input",
        output_schema_id="schema.vendor.output",
        metadata=MappingProxyType({}),
        extensions=MappingProxyType({}),
    )
    return _TaskRequest(
        descriptor=descriptor,
        document=TaskDocument("1.0", TaskGroupNode("root", kind, ())),
        artifacts=ArtifactCatalog(),
        metadata=MappingProxyType({"taskLabel": "comparison"}),
        extensions=MappingProxyType({"vendorTaskOption": True}),
    )


def _service_access() -> ServiceAccess:
    """Create complete unresolved access input for one request fixture."""
    # Keep endpoint, authorization, ordinary request context, and provider scope
    # explicit so the ModelRequest test can verify identity-preserving separation.
    authorization: Authorization = _Authorization(
        OpenIdentifier("authorization.vendor_signature")
    )
    return _ServiceAccess(
        endpoint=UriValue("https://models.example.test/v1", is_absolute=True),
        authorization=authorization,
        headers=Headers((HeaderField("X-Feature", "enabled"),)),
        query=QueryParameters((QueryParameter("region", "east"),)),
        api_version="2026-10-01",
        project_id="project-a",
        tenant_id="tenant-a",
        extensions=MappingProxyType({"accessOption": True}),
    )


def _accept_model_request(request: ModelRequest) -> ModelRequest:
    """Return one request after crossing the static protocol boundary."""
    # Pyright verifies the complete property types at the caller while the runtime
    # check verifies that all required attributes remain structurally present.
    return request


def test_model_request_accepts_custom_structural_implementation() -> None:
    """Verify applications can define complete requests without SDK inheritance."""
    target = _target()
    task = _task()
    access = _service_access()
    metadata: Extensions = MappingProxyType({"traceLabel": "request-a"})
    extensions: Extensions = MappingProxyType({"futureRequestOption": 2})
    request = _CustomModelRequest(target, task, access, metadata, extensions)

    # Structural recognition and exact identities prove the envelope neither
    # registers implementations nor merges independently owned request values.
    assert isinstance(request, ModelRequest)
    assert _accept_model_request(request) is request
    assert request.target is target
    assert request.task is task
    assert request.service_access is access
    assert request.metadata is metadata
    assert request.extensions is extensions


def test_model_request_allows_access_to_remain_unresolved() -> None:
    """Verify absence of a request-level access override remains explicit."""
    request = _CustomModelRequest(
        _target(),
        _task(),
        None,
        MappingProxyType({}),
        MappingProxyType({}),
    )

    # None does not imply anonymous access or a synthesized endpoint; later
    # configuration resolution owns fallback to interaction and client layers.
    assert isinstance(request, ModelRequest)
    assert request.service_access is None
    assert request.metadata == {}
    assert request.extensions == {}


def test_model_request_exposes_only_task_neutral_envelope_fields() -> None:
    """Verify task details, mode, runtime options, and transport stay external."""
    properties = {
        name
        for name, value in vars(ModelRequest).items()
        if isinstance(value, property)
    }

    # The exact surface keeps target, task, access, and preservation channels
    # separate while preventing conversation-specific or runtime-owned leakage.
    assert properties == {
        "target",
        "task",
        "service_access",
        "metadata",
        "extensions",
    }
    for field_name in (
        "messages",
        "generation_parameters",
        "interaction_mode",
        "options",
        "components",
        "protocol_payload",
        "transport",
    ):
        assert field_name not in properties


def test_model_request_requires_the_complete_field_surface() -> None:
    """Verify target and task alone cannot masquerade as a complete request."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteRequest:
        """Intentionally omit access, metadata, and extension properties."""

        target: ModelTarget
        """Target exposed by the incomplete fixture."""

        task: ModelTaskRequest
        """Task exposed without its required sibling request boundaries."""

    request = _IncompleteRequest(_target(), _task())

    # Optional and empty fields still require explicit properties so absence
    # cannot be confused with a deliberately unresolved or empty request value.
    assert not isinstance(request, ModelRequest)
