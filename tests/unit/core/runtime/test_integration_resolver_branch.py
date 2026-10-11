"""Tests for the default integration-resolver branch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import signature
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    CompatibilityPolicy,
    Extensions,
    InteractionMode,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
)
from mconet.core.runtime._integration_resolver_branch import (
    resolve_integration_binding,
)
from mconet.core.runtime._model_integration_resolution_errors import (
    unsupported_model_integration_error,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ModelTargetMatch,
    TaskMatch,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Separate mappings keep one fixture from mutating another fixture's fields.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural model target passed to the resolver."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Structural task descriptor passed to the resolver."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Document:
    """Placeholder task document. This branch does not read it."""

    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class _Task:
    """Structural task whose descriptor is forwarded to the resolver."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog = field(default_factory=ArtifactCatalog)
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Request:
    """Structural request carrying the target and task."""

    target: ModelTarget
    task: ModelTaskRequest
    service_access: ServiceAccess | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Component:
    """Runtime component used as the plan's adapter."""

    descriptor: ComponentDescriptor


class _Resolver:
    """Resolver that returns one prepared plan and records its inputs."""

    def __init__(self, plan: ModelIntegrationPlan) -> None:
        """Store the plan this branch must return unchanged."""
        self._plan = plan
        self.calls: list[tuple[object, object, object, object]] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("resolver", "1.0.0", "application")

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Record the forwarded inputs and return the prepared plan."""
        self.calls.append((target, task, mode, policy))
        return self._plan


def test_default_resolver_forms_the_resolved_plan() -> None:
    """Verify the branch forwards the request and returns the resolver plan."""
    target = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    descriptor = _Descriptor(OpenIdentifier("conversation.generate"))
    request = _Request(target, _Task(descriptor, cast(TaskDocument, _Document())))
    mode = _Mode(OpenIdentifier("unary"))
    policy = CompatibilityPolicy(OpenIdentifier("compatible"))
    adapter = _Component(ComponentDescriptor("adapter", "1.0.0", "application"))
    plan = ModelIntegrationPlan(
        source="resolved_binding",
        binding_id="openai-compatible.chat-completions",
        binding_version="1.0.0",
        match=ModelIntegrationMatch(ModelTargetMatch(True, 1), TaskMatch(True, 1)),
        task_protocol_adapter=adapter,
    )
    resolver = _Resolver(plan)

    # An explicit adapter cannot be supplied to this branch.
    assert tuple(signature(resolve_integration_binding).parameters) == (
        "resolver",
        "request",
        "mode",
        "policy",
    )
    resolved = resolve_integration_binding(
        cast(ModelIntegrationResolver, resolver),
        request,
        mode,
        policy,
    )

    assert resolved is plan
    assert resolved.source == "resolved_binding"
    assert resolver.calls == [(target, descriptor, mode, policy)]


def test_resolver_failure_is_not_replaced_by_a_direct_plan() -> None:
    """Verify a resolver error ends the branch."""
    resolver = _FailingResolver()
    request = _Request(
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("protocol.vendor"),
            NamedModel("vendor-model"),
        ),
        _Task(
            _Descriptor(OpenIdentifier("conversation.generate")),
            cast(TaskDocument, _Document()),
        ),
    )

    error = _capture(
        lambda: resolve_integration_binding(
            cast(ModelIntegrationResolver, resolver),
            request,
            _Mode(OpenIdentifier("unary")),
            CompatibilityPolicy(OpenIdentifier("strict")),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_model_integration"
    assert resolver.calls == 1


class _FailingResolver:
    """Resolver that reports no matching integration."""

    def __init__(self) -> None:
        """Start with no recorded resolve calls."""
        self.calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("resolver", "1.0.0", "application")

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Count the call and fail with the stable unsupported integration error."""
        del target, task, mode, policy
        self.calls += 1
        raise unsupported_model_integration_error()


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
