"""Tests that output assembly delegates to ModelOutputAssembler once."""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal

from mconet.core.domain import (
    ArtifactCatalog,
    Diagnostic,
    Extensions,
    InteractionPhase,
    ModelDescriptor,
    ModelOutput,
    ModelRequest,
    ModelTarget,
    ModelTaskRequest,
    ModelTaskResult,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    TokenUsage,
)
from mconet.core.runtime._model_output_assembly import assemble_interaction_output
from mconet.core.runtime.model_output_assembler import ModelOutputAssembler


class _TaskKind:
    """Container kind for one empty task document."""

    def __init__(self) -> None:
        """Store the kind identity and composition."""
        self.id = OpenIdentifier("task.root")
        self.composition: Literal["container"] = "container"


class _TaskDescriptor:
    """Task descriptor for one structural request or result."""

    def __init__(self, task_type: str) -> None:
        """Store the descriptor fields used by output validation."""
        self.type = OpenIdentifier(task_type)
        self.version = "1.0"
        self.input_schema_id = "schema.vendor.input"
        self.output_schema_id = "schema.vendor.output"
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _TaskValue:
    """Structural task value shared by a request and a result."""

    def __init__(self, task_type: str) -> None:
        """Store one empty task document."""
        kind: TaskNodeKind = _TaskKind()
        descriptor: TaskDescriptor = _TaskDescriptor(task_type)
        self.descriptor = descriptor
        self.document = TaskDocument("1.0", TaskGroupNode("root", kind, ()))
        self.artifacts = ArtifactCatalog()
        self.metadata: Extensions = MappingProxyType({"taskLabel": task_type})
        self.extensions: Extensions = MappingProxyType({})


class _Target:
    """Request target retained by the assembled output."""

    def __init__(self) -> None:
        """Store one named model target."""
        self.service_id = OpenIdentifier("service.vendor")
        self.protocol_id = OpenIdentifier("protocol.vendor")
        self.model: ModelDescriptor = NamedModel("requested-model")
        self.deployment_id = "deployment-primary"
        self.extensions: Extensions = MappingProxyType({})


class _Request:
    """Request whose target must remain the output target."""

    def __init__(self, target: ModelTarget) -> None:
        """Store the request around one task."""
        task: ModelTaskRequest = _TaskValue("vendor.request")
        self.target = target
        self.task = task
        self.service_access = None
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _CountingAssembler(ModelOutputAssembler):
    """Count assemble calls and keep the returned output."""

    def __init__(self) -> None:
        """Start with no recorded assembly."""
        self.calls = 0
        self.result: ModelOutput | None = None

    def assemble(
        self,
        request: ModelRequest,
        parsed_response: ParsedTaskResponse,
        diagnostics: tuple[Diagnostic, ...],
        *,
        output_id: str | None = None,
    ) -> ModelOutput:
        """Record one call and delegate to the real assembler."""
        self.calls += 1
        self.result = super().assemble(
            request,
            parsed_response,
            diagnostics,
            output_id=output_id,
        )
        return self.result


def test_assembly_keeps_each_owner_and_calls_the_assembler_once() -> None:
    """Verify target, status, usage, and diagnostics stay with their owners."""
    target = _Target()
    request: ModelRequest = _Request(target)
    usage = TokenUsage(12, 8, 25)
    status = OutputStatus(OpenIdentifier("completed"))
    result: ModelTaskResult = _TaskValue("vendor.result")
    response = ParsedTaskResponse(result, status, usage=usage)
    diagnostic = Diagnostic(
        "runtime.notice",
        "info",
        InteractionPhase(OpenIdentifier("response_parsing")),
        "Runtime observation.",
    )
    diagnostics = (diagnostic,)
    assembler = _CountingAssembler()

    output = assemble_interaction_output(
        assembler,
        request,
        response,
        diagnostics,
        output_id="output-1",
    )

    assert assembler.calls == 1
    assert output is assembler.result
    assert output.target is target
    assert output.status is status
    assert output.usage is usage
    assert output.diagnostics is diagnostics
    assert output.result is result
    assert output.id == "output-1"
