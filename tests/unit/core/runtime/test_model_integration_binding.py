"""Internal composition and non-registration tests for integration bindings."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError, dataclass, field, fields
from typing import cast

import mconet.core.runtime
from mconet.core.domain import (
    Authorization,
    Extensions,
    Headers,
    InteractionMode,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    TaskDescriptor,
    UriValue,
)
from mconet.core.runtime._model_integration_binding import (
    ModelIntegrationBinding,
    match_binding,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelTargetMatch,
    RuntimeComponent,
    TaskMatch,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match binding-owned diagnostics so a nested fixture failure cannot make
        # an invalid internal composition test pass for the wrong reason.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _empty_extensions() -> Extensions:
    """Create typed empty portable extensions for structural test values."""
    # A factory avoids sharing a mutable fixture dictionary while satisfying
    # the public read-only mapping contract.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque application authorization used by access defaults."""

    kind: OpenIdentifier
    """Open handler-selection discriminator."""


@dataclass(frozen=True, slots=True)
class _ServiceAccess:
    """Complete structural access defaults owned by one test binding."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers
    query: QueryParameters
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target consumed by target matchers."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete structural task descriptor consumed by task matchers."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode consumed together with a task descriptor."""

    id: OpenIdentifier
    """Open mode identity used by the matcher."""


class _TargetMatcher:
    """Matcher stub returning a configured target result."""

    def __init__(self, result: ModelTargetMatch | None) -> None:
        """Store the exact result returned for every test target."""
        # The stub has no registry, I/O, or hidden fallback behavior.
        self._result = result

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Return the configured result after observing a complete target."""
        # Structural access proves the matcher received the target while the
        # fixture deliberately performs no target-dependent selection algorithm.
        assert isinstance(target.service_id, OpenIdentifier)
        return self._result


class _TaskMatcherStub:
    """Matcher stub returning a configured task-and-mode result."""

    def __init__(self, result: TaskMatch | None) -> None:
        """Store the exact result returned for every test task and mode."""
        # The stub remains deterministic and side-effect free.
        self._result = result

    def match(
        self,
        task: TaskDescriptor,
        mode: InteractionMode,
    ) -> TaskMatch | None:
        """Return the configured result after observing both matcher inputs."""
        # Read only open identifiers so the test verifies the complete signature
        # without introducing task or mode support policy.
        assert isinstance(task.type, OpenIdentifier)
        assert isinstance(mode.id, OpenIdentifier)
        return self._result


@dataclass(frozen=True, slots=True)
class _Component:
    """Concrete runtime component carrying immutable descriptor metadata."""

    descriptor: ComponentDescriptor
    """Static component metadata used by binding validation."""


@dataclass(frozen=True, slots=True)
class _MissingDescriptor:
    """Object intentionally lacking RuntimeComponent metadata."""

    label: str
    """Unrelated label proving arbitrary objects are rejected."""


@dataclass(frozen=True, slots=True)
class _MalformedComponent:
    """Structurally matching component with a non-nominal descriptor."""

    descriptor: object
    """Invalid descriptor payload used by nominal metadata tests."""


def _component(name: str) -> _Component:
    """Build one distinguishable plugin component for a named binding role."""
    # Name and version are diagnostics only; concrete object identity, rather
    # than either label, is what the binding stores and later consumers use.
    return _Component(ComponentDescriptor(name, "1.0.0", "plugin"))


def _binding(
    *,
    extensions: Mapping[str, object] | None = None,
) -> ModelIntegrationBinding:
    """Build a complete internal binding with explicit component instances."""
    # Every role receives a distinct instance so tests can detect replacement,
    # reordering, registry lookup, or accidental candidate merging.
    extension_values: Mapping[str, object] = {} if extensions is None else extensions
    return ModelIntegrationBinding(
        id="openai-compatible.conversation",
        version="1.0.0",
        target_matcher=_TargetMatcher(ModelTargetMatch(True, 400)),
        task_matcher=_TaskMatcherStub(TaskMatch(True, 200)),
        task_protocol_adapter=_component("task-adapter"),
        authorization_handlers=(
            _component("bearer-handler"),
            _component("no-authorization-handler"),
        ),
        default_service_access=_ServiceAccess(
            endpoint=UriValue("https://models.example.test", True),
            authorization=_Authorization(OpenIdentifier("authorization.bearer")),
            headers=Headers(),
            query=QueryParameters(),
        ),
        payload_encoders=(_component("json-encoder"),),
        payload_decoders=(
            _component("json-success-decoder"),
            _component("json-error-decoder"),
        ),
        transports=(_component("http-transport"),),
        extensions=extension_values,
    )


def test_model_integration_binding_preserves_explicit_component_combination() -> None:
    """Verify matchers, access defaults, and role candidates remain exact."""
    binding = _binding()
    target = _Target(
        OpenIdentifier("service.openai-compatible"),
        OpenIdentifier("protocol.openai-compatible"),
        NamedModel("model-a"),
    )
    task = _Task(OpenIdentifier("conversation.generate"))
    mode = _Mode(OpenIdentifier("unary"))

    # Matcher objects execute directly without a registry lookup, while every
    # component field contains the exact concrete instances assembled by SDK/plugin code.
    assert binding.target_matcher.match(target) == ModelTargetMatch(True, 400)
    assert binding.task_matcher.match(task, mode) == TaskMatch(True, 200)
    assert binding.task_protocol_adapter.descriptor.name == "task-adapter"
    assert tuple(item.descriptor.name for item in binding.authorization_handlers) == (
        "bearer-handler",
        "no-authorization-handler",
    )
    assert tuple(item.descriptor.name for item in binding.payload_encoders) == (
        "json-encoder",
    )
    assert tuple(item.descriptor.name for item in binding.payload_decoders) == (
        "json-success-decoder",
        "json-error-decoder",
    )
    assert tuple(item.descriptor.name for item in binding.transports) == (
        "http-transport",
    )
    assert binding.default_service_access is not None
    assert binding.default_service_access.endpoint == UriValue(
        "https://models.example.test", True
    )


def test_model_integration_binding_retains_component_identity_and_order() -> None:
    """Verify binding assembly neither reconstructs instances nor reorders candidates."""
    adapter = _component("adapter")
    first_decoder = _component("first-decoder")
    second_decoder = _component("second-decoder")
    binding = ModelIntegrationBinding(
        "binding",
        "1",
        _TargetMatcher(None),
        _TaskMatcherStub(None),
        adapter,
        (),
        None,
        (),
        (first_decoder, second_decoder),
        (),
    )

    # Concrete instance identity is the selection input; descriptor labels never
    # become IDs and tuple order remains exactly as immutable assembly declared it.
    assert binding.task_protocol_adapter is adapter
    assert binding.payload_decoders[0] is first_decoder
    assert binding.payload_decoders[1] is second_decoder
    assert binding.payload_decoders == (first_decoder, second_decoder)


def test_model_integration_binding_is_internal_and_has_no_registry_api() -> None:
    """Verify business-facing module exports and mutable registry methods stay absent."""
    binding = _binding()

    # The type requires an internal module import and is not surfaced from the
    # runtime package or SPI; callers receive resolved plans rather than bindings.
    assert mconet.core.runtime.__all__ == ()
    assert not hasattr(mconet.core.runtime, "ModelIntegrationBinding")
    assert not hasattr(binding, "register")
    assert not hasattr(binding, "add")
    assert not hasattr(binding, "remove")
    assert not hasattr(binding, "component_ids")
    assert not hasattr(binding, "registry")


def test_model_integration_binding_has_frozen_explicit_field_surface() -> None:
    """Verify current executable component roles are named and immutable."""
    binding = _binding()

    # Future streaming, artifact, operation, and capability roles remain absent
    # until their real interfaces exist; current roles are never hidden in a map.
    assert tuple(field.name for field in fields(ModelIntegrationBinding)) == (
        "id",
        "version",
        "target_matcher",
        "task_matcher",
        "task_protocol_adapter",
        "authorization_handlers",
        "default_service_access",
        "payload_encoders",
        "payload_decoders",
        "transports",
        "extensions",
    )
    assert not hasattr(binding, "components")
    assert not hasattr(binding, "artifact_readers")
    assert not hasattr(binding, "stream_framer_factories")
    assert not hasattr(binding, "operation_protocol_adapters")
    _assert_raises(
        FrozenInstanceError,
        lambda: binding.__setattr__("version", "2"),
        "cannot assign to field",
    )


def test_model_integration_binding_snapshots_internal_extensions() -> None:
    """Verify caller changes cannot alter binding extension membership."""
    marker: list[str] = ["opaque"]
    source: dict[str, object] = {"dialect": "vendor", "marker": marker}
    binding = _binding(extensions=source)

    source["dialect"] = "changed"
    source["later"] = True

    # Top-level membership and bindings are detached, while intentionally opaque
    # nested runtime values retain identity for the owning integration code.
    assert binding.extensions == {"dialect": "vendor", "marker": marker}
    assert binding.extensions["marker"] is marker
    assert "later" not in binding.extensions
    assert not hasattr(binding.extensions, "__setitem__")


def test_model_integration_binding_requires_identity_matchers_and_access_shape() -> (
    None
):
    """Verify metadata, matcher behavior, and optional access boundaries."""
    binding = _binding()

    # Validate independent structural boundaries with stable field-specific
    # failures rather than allowing attribute errors during later resolution.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            cast(str, 1),
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "id must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            cast(str, 1),
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "version must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            cast(_TargetMatcher, object()),
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "target_matcher must implement match",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            cast(_TaskMatcherStub, object()),
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "task_matcher must implement match",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            cast(ServiceAccess, object()),
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "default_service_access must implement ServiceAccess or be None",
    )


def test_model_integration_binding_requires_runtime_components_and_descriptors() -> (
    None
):
    """Verify every named role contains concrete components with valid metadata."""
    binding = _binding()

    # A required adapter cannot be an arbitrary object, and a structural object
    # with a malformed descriptor cannot bypass the nominal metadata boundary.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            cast(RuntimeComponent, _MissingDescriptor("adapter")),
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "task_protocol_adapter must implement RuntimeComponent",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            cast(RuntimeComponent, _MalformedComponent("descriptor")),
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "task_protocol_adapter descriptor must be a ComponentDescriptor",
    )

    # Candidate fields require tuple storage and validate every member's shared
    # RuntimeComponent and ComponentDescriptor boundaries independently.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            cast(tuple[RuntimeComponent, ...], []),
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
        ),
        "authorization_handlers must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            (cast(RuntimeComponent, _MissingDescriptor("encoder")),),
            binding.payload_decoders,
            binding.transports,
        ),
        "payload_encoders must implement RuntimeComponent",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            (cast(RuntimeComponent, _MalformedComponent("descriptor")),),
            binding.transports,
        ),
        "payload_decoders descriptor must be a ComponentDescriptor",
    )


def test_model_integration_binding_requires_named_extension_mapping() -> None:
    """Verify internal extensions use mapping storage and string member names."""
    binding = _binding()

    # Named string keys provide deterministic internal lookup without imposing
    # portable JSON restrictions on SDK/plugin-owned opaque runtime values.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
            cast(Mapping[str, object], ()),
        ),
        "extensions must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationBinding(
            binding.id,
            binding.version,
            binding.target_matcher,
            binding.task_matcher,
            binding.task_protocol_adapter,
            binding.authorization_handlers,
            binding.default_service_access,
            binding.payload_encoders,
            binding.payload_decoders,
            binding.transports,
            cast(Mapping[str, object], {1: "invalid"}),
        ),
        "extensions keys must be strings",
    )


class _RecordingTargetMatcher:
    """Target matcher recording its calls and returning a configured value."""

    def __init__(self, result: object, calls: list[str]) -> None:
        """Store the returned value and the shared call log."""
        self._result = result
        self._calls = calls

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Record the call and return the configured value unchecked."""
        del target
        self._calls.append("target")
        return cast(ModelTargetMatch | None, self._result)


class _RecordingTaskMatcher:
    """Task matcher recording its calls and returning a configured value."""

    def __init__(self, result: object, calls: list[str]) -> None:
        """Store the returned value and the shared call log."""
        self._result = result
        self._calls = calls

    def match(self, task: TaskDescriptor, mode: InteractionMode) -> TaskMatch | None:
        """Record the call and return the configured value unchecked."""
        del task, mode
        self._calls.append("task")
        return cast(TaskMatch | None, self._result)


def _matching_binding(
    target_result: object, task_result: object, calls: list[str]
) -> ModelIntegrationBinding:
    """Build a binding whose matchers return the given values."""
    return ModelIntegrationBinding(
        id="fixture",
        version="1.0.0",
        target_matcher=_RecordingTargetMatcher(target_result, calls),
        task_matcher=_RecordingTaskMatcher(task_result, calls),
        task_protocol_adapter=_component("task-adapter"),
        authorization_handlers=(),
        default_service_access=None,
        payload_encoders=(),
        payload_decoders=(),
        transports=(),
    )


def _match_inputs() -> tuple[_Target, _Task, _Mode]:
    """Return one complete target, task, and mode."""
    return (
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("vendor.protocol"),
            NamedModel("fixture-model"),
        ),
        _Task(OpenIdentifier("conversation.generate")),
        _Mode(OpenIdentifier("unary")),
    )


def test_match_binding_combines_both_successful_results_exactly() -> None:
    """Verify the match keeps both result objects and checks target first."""
    calls: list[str] = []
    target_match = ModelTargetMatch(True, 3)
    task_match = TaskMatch(True, 2)
    target, task, mode = _match_inputs()

    match = match_binding(
        _matching_binding(target_match, task_match, calls), target, task, mode
    )

    assert match == ModelIntegrationMatch(target_match, task_match)
    assert match is not None
    assert match.target is target_match
    assert match.task is task_match
    assert calls == ["target", "task"]


def test_match_binding_rejects_without_consulting_the_task_after_a_target_miss() -> (
    None
):
    """Verify None and matched=False targets both stop evaluation."""
    target, task, mode = _match_inputs()
    for target_result in (None, ModelTargetMatch(False, 9)):
        calls: list[str] = []
        binding = _matching_binding(target_result, TaskMatch(True, 1), calls)

        assert match_binding(binding, target, task, mode) is None
        assert calls == ["target"]


def test_match_binding_rejects_a_task_miss() -> None:
    """Verify None and matched=False task results both reject the binding."""
    target, task, mode = _match_inputs()
    for task_result in (None, TaskMatch(False, 9)):
        calls: list[str] = []
        binding = _matching_binding(ModelTargetMatch(True, 1), task_result, calls)

        assert match_binding(binding, target, task, mode) is None
        assert calls == ["target", "task"]


def test_match_binding_rejects_matcher_results_of_another_type() -> None:
    """Verify a matcher cannot return an arbitrary truthy value."""
    target, task, mode = _match_inputs()
    target_binding = _matching_binding(True, TaskMatch(True, 1), [])
    task_binding = _matching_binding(ModelTargetMatch(True, 1), "yes", [])

    _assert_raises(
        TypeError,
        lambda: match_binding(target_binding, target, task, mode),
        "target_matcher must return ModelTargetMatch or None",
    )
    _assert_raises(
        TypeError,
        lambda: match_binding(task_binding, target, task, mode),
        "task_matcher must return TaskMatch or None",
    )
