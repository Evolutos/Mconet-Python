"""Tests for the single public model-request normalization step."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import signature
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    ModelDescriptor,
    ModelRequest,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
)
from mconet.core.runtime._public_input_normalization import normalize_public_input


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep one fixture from mutating another fixture's fields.
    return {}


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target whose service id can be made invalid on purpose."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for an empty open-task document root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"] = "container"


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Open task descriptor that is not the conversation task family."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request that can bypass the builder's successful validation."""

    target: ModelTarget
    task: ModelTaskRequest
    service_access: None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Open task request accepted by the task-neutral request validator."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


def _task() -> ModelTaskRequest:
    """Create one valid open task that normalization must not rebuild."""
    # An empty root is enough for the common task boundary. Conversation scope
    # checks belong to the later R1 validator stage.
    return _Task(
        _Descriptor(OpenIdentifier("vendor.document-compare")),
        TaskDocument(
            "1.0",
            TaskGroupNode("root", _NodeKind(OpenIdentifier("task.root")), ()),
        ),
        ArtifactCatalog(),
    )


def _request(service_id: str) -> ModelRequest:
    """Build one public request around the shared open task."""
    # The builder publishes an immutable request. Normalization must keep it.
    target: ModelTarget = _Target(
        OpenIdentifier(service_id),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    return ModelRequestBuilder(target, _task()).build()


def test_normalization_accepts_only_the_public_request() -> None:
    """Verify the step has no client, component, or second-input parameter."""
    # Configuration merge and component resolution are later stages. This step
    # cannot write a normalized request back onto a client.
    assert tuple(signature(normalize_public_input).parameters) == ("request",)


def test_normalization_returns_the_same_request_once() -> None:
    """Verify one public request stays the only normalized request."""
    request = _request("service.vendor")
    first = normalize_public_input(request)
    second = normalize_public_input(request)

    # Repeating the step does not allocate a replacement envelope or detach the
    # task from the caller's request.
    assert first is request
    assert second is request
    assert first.task is request.task
    assert first.target is request.target


def test_invalid_public_input_fails_without_a_replacement_request() -> None:
    """Verify an invalid request raises instead of being rewritten."""
    request = _Request(
        _Target(
            OpenIdentifier(""),
            OpenIdentifier("protocol.vendor"),
            NamedModel("vendor-model"),
        ),
        _task(),
    )

    error = _capture(lambda: normalize_public_input(request))

    # The original object remains the caller's request. Failure does not invent
    # a fallback target, task, or access value.
    assert isinstance(error, ValueError)
    assert request.target.service_id.value == ""
