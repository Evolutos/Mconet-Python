"""Tests for the explicit-adapter integration branch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import signature
from typing import cast

from mconet.core.domain import (
    ArtifactCatalog,
    Extensions,
    InteractionMode,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
)
from mconet.core.runtime._direct_adapter_branch import resolve_direct_adapter
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskProtocolAdapter,
    TransportResponseMetadata,
)


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
    """Structural model target read by the direct branch."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Structural task descriptor read by the direct branch."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Document:
    """Placeholder task document. The direct branch does not read it."""

    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class _Task:
    """Structural task whose descriptor is the only field the branch reads."""

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


class _Adapter:
    """Adapter whose supports answer is fixed by the test."""

    def __init__(self, answer: bool) -> None:
        """Store the support answer."""
        self._answer = answer
        self.supports_calls = 0
        self.other_calls = 0

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("direct-adapter", "1.0.0", "application")

    def supports(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> bool:
        """Count one support check and return the configured answer."""
        del target, task, mode
        self.supports_calls += 1
        return self._answer

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Record a call that the direct branch must not make."""
        del request, access, mode
        self.other_calls += 1
        raise AssertionError("prepare_plan must not be called.")

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Record a call that the direct branch must not make."""
        del request, plan
        self.other_calls += 1
        raise AssertionError("build_request must not be called.")

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Record a call that the direct branch must not make."""
        del response
        self.other_calls += 1
        raise AssertionError("parse_response must not be called.")

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> ModelInteractionError | None:
        """Record a call that the direct branch must not make."""
        del error, metadata
        self.other_calls += 1
        raise AssertionError("parse_error must not be called.")


def _request() -> _Request:
    """Return one structural request for the direct branch."""
    return _Request(
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


def test_explicit_adapter_forms_a_direct_plan_without_a_resolver() -> None:
    """Verify the branch keeps the injected adapter and has no resolver slot."""
    adapter = _Adapter(True)
    request = _request()
    mode = _Mode(OpenIdentifier("unary"))

    # A resolver cannot be supplied, so this branch cannot fall back.
    assert tuple(signature(resolve_direct_adapter).parameters) == (
        "adapter",
        "request",
        "mode",
    )
    plan = resolve_direct_adapter(cast(TaskProtocolAdapter, adapter), request, mode)

    assert plan.source == "direct_adapter"
    assert plan.task_protocol_adapter is adapter
    assert plan.binding_id is None
    assert adapter.supports_calls == 1
    assert adapter.other_calls == 0


def test_rejected_adapter_does_not_continue() -> None:
    """Verify an unsupported explicit adapter fails inside this branch."""
    adapter = _Adapter(False)

    error = _capture(
        lambda: resolve_direct_adapter(
            cast(TaskProtocolAdapter, adapter),
            _request(),
            _Mode(OpenIdentifier("unary")),
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_model_integration"
    assert adapter.supports_calls == 1
    assert adapter.other_calls == 0
