"""Validation failure does not call transport, resolver, or credentials."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    CompatibilityPolicy,
    Extensions,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequestBuilder,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
)
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._validation_failure_gate import run_validation_gate
from mconet.core.spi import (
    AuthorizationContext,
    ComponentDescriptor,
    CredentialValue,
    ModelIntegrationPlan,
    TransportContext,
    TransportRequest,
    TransportResponse,
)


def _empty_extensions() -> Extensions:
    """Return one empty extension mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target for one public request."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for an empty task document."""

    id: OpenIdentifier
    composition: Literal["container"] = "container"


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Task descriptor outside the R1 conversation type."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Task request whose type is not a conversation."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Transport:
    """Transport that records a send."""

    def __init__(self) -> None:
        """Start with no sends."""
        self.descriptor = ComponentDescriptor("transport", "1.0.0", "application")
        self.calls: list[str] = []

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Record a send that validation must not reach."""
        del request, context
        self.calls.append("send")
        raise AssertionError("transport was called")


class _Resolver:
    """Resolver that records a resolve."""

    def __init__(self) -> None:
        """Start with no resolutions."""
        self.descriptor = ComponentDescriptor("resolver", "1.0.0", "application")
        self.calls: list[str] = []

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Record a resolution that validation must not reach."""
        del target, task, mode, policy
        self.calls.append("resolve")
        raise AssertionError("resolver was called")


class _Credential:
    """Credential source that records a read."""

    def __init__(self) -> None:
        """Start with no reads."""
        self.calls: list[str] = []

    async def resolve(self, context: AuthorizationContext) -> CredentialValue:
        """Record a read that validation must not reach."""
        del context
        self.calls.append("resolve")
        raise AssertionError("credential source was called")


def test_validation_failure_does_not_call_later_stages() -> None:
    """Verify an unsupported task stops before transport, resolver, and credentials."""
    task: ModelTaskRequest = _Task(
        _Descriptor(OpenIdentifier("vendor.document-compare")),
        TaskDocument(
            "1.0",
            TaskGroupNode(
                "root",
                _NodeKind(OpenIdentifier("task.root")),
                (),
            ),
        ),
        ArtifactCatalog(),
    )
    request = ModelRequestBuilder(
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("protocol.vendor"),
            NamedModel("vendor-model"),
        ),
        task,
    ).build()
    transport = _Transport()
    resolver = _Resolver()
    credential = _Credential()
    machine = InteractionTerminalMachine()

    error = _capture(
        lambda: run_validation_gate(
            request,
            _Mode(OpenIdentifier("unary")),
            transport,
            resolver,
            credential,
            machine,
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_task"
    assert transport.calls == []
    assert resolver.calls == []
    assert credential.calls == []
    assert machine.state is not None
    assert machine.state.failed is True


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
