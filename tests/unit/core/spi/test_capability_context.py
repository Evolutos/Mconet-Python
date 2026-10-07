"""Read-only structural contract tests for capability processing context."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    Extensions,
    Headers,
    InteractionMode,
    MediaType,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    TaskDescriptor,
    UriValue,
)
from mconet.core.spi import (
    BodySigningRequirement,
    CapabilityContext,
    ComponentSelectionResolution,
    DecoderSelection,
    EncoderSelection,
    ProtocolExecutionPlan,
    TransportRequestPlan,
    TransportSelection,
)


def _empty_extensions() -> Extensions:
    """Create independent empty JSON mappings for structural fixtures."""
    # A fresh mapping prevents unrelated target, task, and context values from
    # sharing mutable fixture state through their read-only protocol surfaces.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture required by the transport request plan."""

    kind: OpenIdentifier
    """Open handler-selection discriminator not interpreted by this context."""


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target for one capability context."""

    service_id: OpenIdentifier
    """Open service identity observed by capability processing."""

    protocol_id: OpenIdentifier
    """Open interaction protocol identity observed by capability processing."""

    model: ModelDescriptor
    """Exact model descriptor selected for the interaction."""

    deployment_id: str | None = None
    """Optional service deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown target fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete structural task descriptor for one capability context."""

    type: OpenIdentifier
    """Open task identity observed by capability processing."""

    version: str | None = None
    """Optional producer task version."""

    input_schema_id: str | None = None
    """Optional task input schema identity."""

    output_schema_id: str | None = None
    """Optional task output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive task facts."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown task fields retained without interpretation."""


@dataclass(frozen=True, slots=True)
class _Mode:
    """Application-owned open interaction mode implementation."""

    id: OpenIdentifier
    """Open execution mode identity selected by the caller entry point."""


@dataclass(frozen=True, slots=True)
class _Context:
    """Immutable application context proving inheritance-free conformance."""

    target: ModelTarget
    """Exact current interaction target."""

    task: TaskDescriptor
    """Exact current task descriptor."""

    interaction_mode: InteractionMode
    """Exact current interaction mode."""

    execution_plan: ProtocolExecutionPlan
    """Exact side-effect-free protocol plan."""

    selected_components: ComponentSelectionResolution
    """Exact uniquely selected component snapshot."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable versioned context facts."""


class _PropertyContext:
    """Custom context exposing every contract value through properties."""

    def __init__(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        interaction_mode: InteractionMode,
        execution_plan: ProtocolExecutionPlan,
        selected_components: ComponentSelectionResolution,
        extensions: Extensions,
    ) -> None:
        """Store exact context facts behind private implementation state."""
        # Private storage proves collectors do not depend on dataclasses, public
        # writable attributes, SDK inheritance, or a Runtime-owned base class.
        self._target = target
        self._task = task
        self._interaction_mode = interaction_mode
        self._execution_plan = execution_plan
        self._selected_components = selected_components
        self._extensions = extensions

    @property
    def target(self) -> ModelTarget:
        """Return the exact interaction target."""
        # No target reconstruction or integration lookup occurs on observation.
        return self._target

    @property
    def task(self) -> TaskDescriptor:
        """Return the exact task descriptor."""
        # Task identity remains separate from source documents collected later.
        return self._task

    @property
    def interaction_mode(self) -> InteractionMode:
        """Return the exact public-entry-point interaction mode."""
        # Capability processing cannot replace the selected execution lifecycle.
        return self._interaction_mode

    @property
    def execution_plan(self) -> ProtocolExecutionPlan:
        """Return the exact immutable protocol plan."""
        # Plan observation performs no adapter call or network operation.
        return self._execution_plan

    @property
    def selected_components(self) -> ComponentSelectionResolution:
        """Return the exact uniquely selected component snapshot."""
        # No candidate, default, or global component lookup is performed here.
        return self._selected_components

    @property
    def extensions(self) -> Extensions:
        """Return the exact read-only portable context extensions."""
        # Unknown values remain explicit data and never become component entries.
        return self._extensions


def _accept_context(context: CapabilityContext) -> CapabilityContext:
    """Return one context after crossing the statically typed protocol boundary."""
    # Pyright verifies nested contract types while runtime recognition proves
    # custom implementations need no SDK superclass or registration step.
    return context


def _execution_plan() -> ProtocolExecutionPlan:
    """Build one complete immutable unary JSON/HTTP protocol plan."""
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    transport_plan = TransportRequestPlan(
        endpoint=UriValue("https://models.example.test", True),
        path="/v1/responses",
        method="POST",
        headers=Headers(),
        query=QueryParameters(),
        authorization=authorization,
        body_signing_requirement=BodySigningRequirement(),
    )
    json_media_type = MediaType("application", "json")

    # The plan fixes declared selection facts only and never resolves components
    # or performs I/O while the capability context exposes it.
    return ProtocolExecutionPlan(
        transport_plan=transport_plan,
        payload_encoder=EncoderSelection(json_media_type, "protocol.request"),
        success_decoder=DecoderSelection(json_media_type, "protocol.response"),
        error_decoder=DecoderSelection(json_media_type, "protocol.error"),
        transport=TransportSelection(OpenIdentifier("http")),
    )


def _context_values() -> tuple[
    _Target,
    _Task,
    _Mode,
    ProtocolExecutionPlan,
    ComponentSelectionResolution,
]:
    """Build all independently observable current-interaction context values."""
    target = _Target(
        service_id=OpenIdentifier("service.example"),
        protocol_id=OpenIdentifier("protocol.example"),
        model=NamedModel("model-a"),
        deployment_id="deployment-a",
    )
    task = _Task(
        type=OpenIdentifier("conversation.generate"),
        version="1",
        input_schema_id="conversation.request",
        output_schema_id="conversation.response",
    )
    mode = _Mode(OpenIdentifier("unary"))
    plan = _execution_plan()
    selected = ComponentSelectionResolution()

    # Returning separate values lets tests prove context implementations retain
    # identity instead of reconstructing or widening any interaction snapshot.
    return target, task, mode, plan, selected


def test_capability_context_preserves_exact_current_interaction_values() -> None:
    """Verify every context property retains its source object by identity."""
    target, task, mode, plan, selected = _context_values()
    context = _Context(target, task, mode, plan, selected)

    # Structural conformance and typed use observe one fixed interaction without
    # copying plans or selecting another component set.
    assert isinstance(context, CapabilityContext)
    assert _accept_context(context) is context
    assert context.target is target
    assert context.task is task
    assert context.interaction_mode is mode
    assert context.execution_plan is plan
    assert context.selected_components is selected


def test_capability_context_accepts_read_only_property_implementation() -> None:
    """Verify context conformance is independent of concrete storage style."""
    target, task, mode, plan, selected = _context_values()
    extensions: Extensions = MappingProxyType({"collectorScope": "current-interaction"})
    context = _PropertyContext(
        target,
        task,
        mode,
        plan,
        selected,
        extensions,
    )

    # Properties expose exact immutable/read-only values without granting Core
    # ownership of application storage or requiring mutation methods.
    assert isinstance(context, CapabilityContext)
    assert _accept_context(context) is context
    assert context.selected_components is selected
    assert context.extensions is extensions


def test_capability_context_exposes_only_selected_component_snapshot() -> None:
    """Verify candidates and unselected component sources stay invisible."""
    target, task, mode, plan, selected = _context_values()
    context = _Context(target, task, mode, plan, selected)

    # The exact field surface prevents collectors/providers from observing or
    # choosing Binding, Client, SDK-default, or registry candidates themselves.
    assert tuple(field.name for field in fields(_Context)) == (
        "target",
        "task",
        "interaction_mode",
        "execution_plan",
        "selected_components",
        "extensions",
    )
    assert not hasattr(context, "component_candidates")
    assert not hasattr(context, "binding")
    assert not hasattr(context, "client_components")
    assert not hasattr(context, "sdk_defaults")
    assert not hasattr(context, "registry")


def test_capability_context_excludes_resolution_inputs_and_outputs() -> None:
    """Verify provider lists, requirements, policy, and result remain separate."""
    target, task, mode, plan, selected = _context_values()
    context = _Context(target, task, mode, plan, selected)

    # The context is shared read-only input; placing mutable resolver state or its
    # output inside it would create cycles and hidden order-dependent behavior.
    assert not hasattr(context, "requirements")
    assert not hasattr(context, "providers")
    assert not hasattr(context, "compatibility_policy")
    assert not hasattr(context, "capability_resolution")
    assert not hasattr(context, "network_client")


def test_capability_context_requires_complete_structural_surface() -> None:
    """Verify partial context-like objects do not satisfy the public protocol."""

    @dataclass(frozen=True, slots=True)
    class _MissingSelectedComponents:
        """Intentionally omit the required selected snapshot property."""

        target: ModelTarget
        task: TaskDescriptor
        interaction_mode: InteractionMode
        execution_plan: ProtocolExecutionPlan
        extensions: Extensions

    target, task, mode, plan, _ = _context_values()
    incomplete = _MissingSelectedComponents(target, task, mode, plan, {})

    # Empty selected membership is valid only when represented by the dedicated
    # snapshot value; absence would erase whether component selection completed.
    assert not isinstance(incomplete, CapabilityContext)
    assert not isinstance(cast(object, plan), CapabilityContext)
