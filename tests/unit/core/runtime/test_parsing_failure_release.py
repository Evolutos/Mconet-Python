"""A parsing failure still releases the interaction context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

from mconet.core.domain import (
    ArtifactCatalog,
    CompatibilityPolicy,
    Extensions,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequestBuilder,
    ModelTaskRequest,
    NamedModel,
    OpenIdentifier,
    ResolvedInteractionResourceLimits,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
)
from mconet.core.runtime._interaction_context import InteractionContext
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._parsing_failure_release import run_response_parsing
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.core.spi import (
    AuthorizationHandlerResolver,
    CapabilityResolution,
    ComponentDescriptor,
    ComponentSelectionResolution,
    ErasedRuntimeValue,
    InteractionExecutionComponents,
    ModelIntegrationPlan,
    PayloadDecoder,
    PayloadEncoder,
    ServiceAccessResolver,
    TaskProtocolAdapter,
    Transport,
    TransportResponseMetadata,
)


def _empty_extensions() -> Extensions:
    """Return one empty extension mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target stored on the interaction request."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _NodeKind:
    """Container kind for an empty task document."""

    id: OpenIdentifier
    composition: Literal["container"] = "container"


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Task descriptor for the context's request."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Task request held by the interaction context."""

    descriptor: TaskDescriptor
    document: TaskDocument
    artifacts: ArtifactCatalog
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Adapter:
    """Adapter whose parser failure includes text that must not leak."""

    def __init__(self) -> None:
        """Store adapter metadata."""
        self.descriptor = ComponentDescriptor("adapter", "1.0.0", "application")

    def supports(self, *values: object) -> bool:
        """Accept the fixture."""
        del values
        return True

    def prepare_plan(self, *values: object) -> object:
        """Do not plan in this failure test."""
        del values
        return object()

    def build_request(self, *values: object) -> object:
        """Do not build a request in this failure test."""
        del values
        return object()

    def parse_response(self, response: ErasedRuntimeValue) -> object:
        """Fail without copying the payload into a stable message."""
        del response
        raise RuntimeError("mconet-test-bearer-token-not-secret")

    def parse_error(
        self,
        error: ErasedRuntimeValue,
        metadata: TransportResponseMetadata,
    ) -> None:
        """Record an error parse that this stage must not perform."""
        del error, metadata
        return None


def test_parsing_failure_releases_the_interaction_context() -> None:
    """Verify a parse error drops callbacks and the request reference."""
    target = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    task: ModelTaskRequest = _Task(
        _Descriptor(OpenIdentifier("conversation.generate")),
        TaskDocument(
            "1.0",
            TaskGroupNode("root", _NodeKind(OpenIdentifier("task.root")), ()),
        ),
        ArtifactCatalog(),
    )
    request = ModelRequestBuilder(target, task).build()
    context = InteractionContext(
        request,
        ResolvedInteractionConfiguration(
            target,
            None,
            CompatibilityPolicy(OpenIdentifier("strict")),
            ResolvedInteractionResourceLimits(100, 200, 300),
            None,
        ),
    )
    context.add_callback(lambda: None)
    unused = object()
    components = InteractionExecutionComponents(
        integration_plan=cast(ModelIntegrationPlan, unused),
        component_selection=cast(ComponentSelectionResolution, unused),
        resource_limits=ResolvedInteractionResourceLimits(100, 200, 300),
        task_protocol_adapter=cast(TaskProtocolAdapter, _Adapter()),
        service_access_resolver=cast(ServiceAccessResolver, unused),
        payload_encoder=cast(PayloadEncoder, unused),
        success_payload_decoder=cast(PayloadDecoder, unused),
        error_payload_decoder=cast(PayloadDecoder, unused),
        transport=cast(Transport, unused),
        authorization_handler_resolver=cast(AuthorizationHandlerResolver, unused),
        authorization_handlers=(),
        capability_resolution=cast(CapabilityResolution, unused),
    )
    machine = InteractionTerminalMachine()
    try:
        run_response_parsing(
            components,
            ErasedRuntimeValue(OpenIdentifier("json.value"), {"ok": False}),
            context,
            machine,
        )
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected parsing to fail.")

    assert raised.code == "response_parsing_failed"
    assert "mconet-test-bearer-token-not-secret" not in raised.message
    assert context.released is True
    assert context.callback_count == 0
    assert machine.state is not None
    assert machine.state.failed is True
    released = _capture(lambda: context.request)
    assert isinstance(released, ModelInteractionError)
    assert released.code == "interaction_context_released"


def _capture(action: object) -> BaseException:
    """Run one action and return the exception it raises."""
    from collections.abc import Callable

    if not isinstance(action, Callable):
        raise AssertionError("Expected a callable.")
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
