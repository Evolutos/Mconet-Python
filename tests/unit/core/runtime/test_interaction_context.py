"""Exclusivity tests for the per-interaction context."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import signature
from typing import Literal, cast
from uuid import UUID

import mconet.client
import mconet.core.runtime
from mconet.core.domain import (
    ArtifactCatalog,
    CompatibilityPolicy,
    Extensions,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
)
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep fixtures from sharing mutable extension state.
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
    """Structural target retained by a request and a resolved configuration."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _TaskDescriptor:
    """Structural task descriptor exposing the full open field surface."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for an empty task-document root."""

    id: OpenIdentifier
    composition: Literal["leaf", "container"] = "container"


@dataclass(frozen=True, slots=True)
class _Task:
    """Structural task request carried inside the interaction envelope."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural model request used as one interaction input."""

    target: ModelTarget
    task: ModelTaskRequest
    service_access: ServiceAccess | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


class _ClientHolder:
    """Stand-in client that could retain contexts if the API allowed it."""

    def __init__(self) -> None:
        """Start with no stored interactions."""
        # An empty collection makes any accidental registration observable.
        self.contexts: list[InteractionContext] = []


def _request() -> _Request:
    """Create one structural request without executing validation."""
    # Context construction stores the request; it does not require a built
    # conversation document or a validated envelope.
    task = _Task(
        _TaskDescriptor(OpenIdentifier("conversation.generate")),
        TaskDocument(
            "1.0",
            TaskGroupNode(
                "root",
                cast(TaskNodeKind, _NodeKind(OpenIdentifier("task.root"))),
                (),
            ),
        ),
        ArtifactCatalog(),
    )
    return _Request(
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("protocol.vendor"),
            NamedModel("model-a"),
        ),
        task,
    )


def _configuration(target: ModelTarget) -> ResolvedInteractionConfiguration:
    """Create a resolved configuration for the same target as the request."""
    # Limits and policy are concrete so the context stores a finished selection
    # rather than a client options object.
    return ResolvedInteractionConfiguration(
        target,
        None,
        CompatibilityPolicy(OpenIdentifier("compatible")),
        ResolvedInteractionResourceLimits(100, 200, 300),
        None,
    )


def test_context_binds_only_request_and_configuration() -> None:
    """Verify the constructor cannot accept or store a client."""
    parameters = signature(InteractionContext).parameters

    # Client configuration, components, and monitors are absent on purpose.
    # A later client must keep its own fields and never receive this object.
    assert tuple(parameters) == ("request", "configuration")
    assert InteractionContext.__slots__ == (
        "_callbacks",
        "_configuration",
        "_identity",
        "_released",
        "_request",
    )
    assert "InteractionContext" not in mconet.core.runtime.__all__
    assert not hasattr(mconet.core.runtime, "InteractionContext")
    assert not hasattr(mconet.client, "InteractionContext")


def test_each_interaction_receives_an_exclusive_context() -> None:
    """Verify equal inputs still allocate distinct, unshared contexts."""
    request = _request()
    configuration = _configuration(request.target)
    client = _ClientHolder()
    first = InteractionContext(request, configuration)
    second = InteractionContext(request, configuration)

    # The same request and configuration may be read twice. Each call still
    # owns a new context, and the stand-in client is never given either one.
    assert first is not second
    assert first.identity != second.identity
    assert isinstance(first.identity, UUID)
    assert first.request is request
    assert second.request is request
    assert first.configuration is configuration
    assert second.configuration is configuration
    assert client.contexts == []


def test_context_is_not_retained_by_its_module_or_class() -> None:
    """Verify construction records the context only in the caller's variable."""
    request = _request()
    configuration = _configuration(request.target)
    context = InteractionContext(request, configuration)
    module = sys.modules[InteractionContext.__module__]
    namespace = (*vars(module).values(), *vars(InteractionContext).values())

    # A client, registry, or class attribute that kept this instance would show
    # up beside the type's functions. The caller's variable is the only owner.
    assert context not in namespace
    for value in namespace:
        if isinstance(value, (list, tuple, set, frozenset)):
            assert context not in value
        if isinstance(value, dict):
            assert context not in value
            assert context not in value.values()


def test_context_rejects_a_non_request_and_a_non_configuration() -> None:
    """Verify storage rejects values that are not the two interaction inputs."""
    request = _request()
    configuration = _configuration(request.target)

    request_error = _capture(
        lambda: InteractionContext(cast(ModelRequest, object()), configuration)
    )
    configuration_error = _capture(
        lambda: InteractionContext(
            request, cast(ResolvedInteractionConfiguration, object())
        )
    )

    assert isinstance(request_error, TypeError)
    assert "ModelRequest" in str(request_error)
    assert isinstance(configuration_error, TypeError)
    assert "ResolvedInteractionConfiguration" in str(configuration_error)


def test_release_drops_callbacks_and_one_shot_references() -> None:
    """Verify termination removes listeners, the request, and the configuration."""
    request = _request()
    configuration = _configuration(request.target)
    context = InteractionContext(request, configuration)
    identity = context.identity
    calls: list[str] = []

    def _callback() -> None:
        calls.append("called")

    context.add_callback(_callback)
    assert context.callback_count == 1

    context.release()
    context.release()

    request_error = _capture(lambda: context.request)
    configuration_error = _capture(lambda: context.configuration)
    callback_error = _capture(lambda: context.add_callback(_callback))

    assert context.released is True
    assert context.callback_count == 0
    assert calls == []
    assert context.identity == identity
    assert isinstance(request_error, ModelInteractionError)
    assert isinstance(configuration_error, ModelInteractionError)
    assert isinstance(callback_error, ModelInteractionError)
    assert request_error.code == "interaction_context_released"
    assert configuration_error.code == "interaction_context_released"
    assert callback_error.code == "interaction_context_released"
