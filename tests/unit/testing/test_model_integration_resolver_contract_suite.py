"""Branch and boundary tests for ModelIntegrationResolverContractSuite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast, get_type_hints

from mconet.core.domain import (
    CompatibilityPolicy,
    ErrorCategory,
    Extensions,
    InteractionMode,
    InteractionPhase,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ModelTargetMatch,
    TaskMatch,
)
from mconet.testing import (
    ComponentCallRecorder,
    ModelIntegrationResolverContractSuite,
    StubModelIntegrationResolver,
)


def _empty_extensions() -> Extensions:
    """Create independent portable storage for structural fixture values."""
    # Fresh mappings make mutation or replacement observable per input instead
    # of allowing separate fixture values to share caller-owned state.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural target supplied to resolver contract cases."""

    service_id: OpenIdentifier
    """Open model service identifier."""

    protocol_id: OpenIdentifier
    """Open interaction protocol identifier."""

    model: ModelDescriptor
    """Validated structural model descriptor."""

    deployment_id: str | None = None
    """Optional provider deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable unknown target fields."""


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete structural task descriptor supplied to resolver cases."""

    type: OpenIdentifier
    """Open task identity."""

    version: str | None = None
    """Optional task contract version."""

    input_schema_id: str | None = None
    """Optional input schema identity."""

    output_schema_id: str | None = None
    """Optional output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable descriptive task metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable unknown task fields."""


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural open interaction mode used by resolver cases."""

    id: OpenIdentifier
    """Open execution-mode identifier."""


@dataclass(frozen=True, slots=True)
class _Component:
    """Minimal concrete runtime component retained by fixture plans."""

    descriptor: ComponentDescriptor
    """Immutable metadata satisfying RuntimeComponent."""


class _RecordingResolver:
    """Structural resolver recording one exact call and configured outcome."""

    __slots__ = ("_calls", "_descriptor", "_error", "_recorder", "_result")

    def __init__(
        self,
        result: ModelIntegrationPlan,
        recorder: ComponentCallRecorder,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Retain one result or failure and initialize exact call evidence."""
        self._descriptor = ComponentDescriptor(
            "Recording integration resolver", "1", "application"
        )
        self._result = result
        self._error = error
        self._recorder = recorder
        self._calls: list[
            tuple[
                ModelTarget,
                TaskDescriptor,
                InteractionMode,
                CompatibilityPolicy,
            ]
        ] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable resolver metadata."""
        # Return the exact constructor-owned value so suite initialization cannot
        # observe generated or replaceable metadata.
        return self._descriptor

    @property
    def calls(
        self,
    ) -> tuple[
        tuple[
            ModelTarget,
            TaskDescriptor,
            InteractionMode,
            CompatibilityPolicy,
        ],
        ...,
    ]:
        """Return an immutable snapshot of exact resolution inputs."""
        # Tuple conversion prevents the test itself from mutating recorded
        # evidence while retaining every caller-owned input by identity.
        return tuple(self._calls)

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Record the exact input tuple, then return or raise once."""
        # Record before outcome delivery so both successful and failing branches
        # prove that the resolver was invoked once with the complete tuple.
        self._recorder.record("resolve_model_integration")
        self._calls.append((target, task, mode, policy))
        if self._error is not None:
            raise self._error
        return self._result


class _MalformedResultResolver:
    """Claim the resolver signature while returning an invalid result."""

    descriptor = ComponentDescriptor("Malformed resolver", "1", "application")
    """Valid metadata isolates successful-result validation."""

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Discard valid inputs and return a dynamically malformed result."""
        # Dynamic casting keeps the invalid value behind the declared protocol
        # signature so the suite's runtime result check is exercised directly.
        del target, task, mode, policy
        return cast(ModelIntegrationPlan, object())


class _IncompleteResolver:
    """Component-shaped object intentionally missing resolve behavior."""

    descriptor = ComponentDescriptor("Incomplete resolver", "1", "application")
    """Valid metadata keeps protocol incompleteness isolated."""


class _InvalidDescriptorResolver:
    """Complete resolver surface exposing malformed component metadata."""

    descriptor = cast(ComponentDescriptor, object())
    """Invalid metadata used only for constructor rejection."""

    def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Discard inputs and return a valid plan if called unexpectedly."""
        # Constructor validation must fail on metadata before this behavior can
        # run, so returning a valid plan isolates the intended invalid field.
        del target, task, mode, policy
        return _resolved_plan()


class _AsyncResolver:
    """Expose an invalid asynchronous integration resolve operation."""

    descriptor = ComponentDescriptor("Async resolver", "1", "application")
    """Valid metadata keeps synchronous-boundary rejection isolated."""

    async def resolve(
        self,
        target: ModelTarget,
        task: TaskDescriptor,
        mode: InteractionMode,
        policy: CompatibilityPolicy,
    ) -> ModelIntegrationPlan:
        """Return a valid plan asynchronously if called unexpectedly."""
        # The suite must reject the coroutine function without invoking it and
        # therefore without allocating an unawaited coroutine object.
        del target, task, mode, policy
        return _resolved_plan()


def _target() -> _Target:
    """Build one complete valid model target."""
    # Distinct target dimensions prove the suite forwards separate service,
    # protocol, model, deployment, and extension facts without reconstruction.
    return _Target(
        OpenIdentifier("service.fixture"),
        OpenIdentifier("protocol.fixture"),
        NamedModel(
            "model-fixture",
            family=OpenIdentifier("model.family.fixture"),
        ),
        deployment_id="deployment-a",
        extensions={"target.region": "east"},
    )


def _task() -> _Task:
    """Build one complete valid task descriptor."""
    # Populate every optional channel so public validation and exact identity
    # forwarding cover the descriptor's complete structural boundary.
    return _Task(
        OpenIdentifier("conversation.generate"),
        version="1.0.0",
        input_schema_id="schema://input",
        output_schema_id="schema://output",
        metadata={"task.variant": "standard"},
    )


def _mode() -> _Mode:
    """Build one valid open unary interaction mode."""
    # An ordinary structural value proves no SDK enum or concrete base class is
    # required by the contract suite.
    return _Mode(OpenIdentifier("unary"))


def _policy() -> CompatibilityPolicy:
    """Build one immutable compatibility policy."""
    # Use the nominal public value because resolver policy is a closed input
    # carrier even though its mode identifier remains forward-compatible.
    return CompatibilityPolicy(OpenIdentifier("compatible"))


def _component(name: str) -> _Component:
    """Build one runtime component with diagnostic metadata."""
    # Component identity, not descriptor text, is retained by integration plans;
    # the name exists only to make fixture failures readable.
    return _Component(ComponentDescriptor(name, "1", "application"))


def _direct_plan() -> ModelIntegrationPlan:
    """Build the minimal valid direct-adapter integration plan."""
    # Direct provenance intentionally excludes binding metadata, match facts,
    # default access, and every binding-owned candidate tuple.
    return ModelIntegrationPlan(
        "direct_adapter",
        None,
        None,
        None,
        _component("Direct adapter"),
    )


def _resolved_plan() -> ModelIntegrationPlan:
    """Build one complete resolved-binding integration plan."""
    # Independent successful target and task results preserve exact provenance
    # without exposing an internal binding object or aggregate match score.
    return ModelIntegrationPlan(
        "resolved_binding",
        "binding.fixture.conversation",
        "1.0.0",
        ModelIntegrationMatch(
            ModelTargetMatch(True, 400),
            TaskMatch(True, 200),
        ),
        _component("Resolved adapter"),
        extensions={"binding.owner": "fixture"},
    )


def _resolution_error(code: str) -> ModelInteractionError:
    """Build one normalized pre-interaction resolver failure."""
    # Missing support and ambiguous configuration use distinct stable categories
    # while sharing the same safe pre-interaction phase and public message.
    category = (
        "unsupported_feature"
        if code == "unsupported_model_integration"
        else "invalid_component_configuration"
    )
    return ModelInteractionError(
        ErrorCategory(OpenIdentifier(category)),
        InteractionPhase(OpenIdentifier("model_integration_resolution")),
        code,
        "Model integration resolution failed.",
    )


def _inputs() -> tuple[_Target, _Task, _Mode, CompatibilityPolicy]:
    """Build one complete independent resolver input tuple."""
    # Fresh values on each call prevent negative tests from sharing mutation or
    # accidentally passing because a prior validation retained input state.
    return (_target(), _task(), _mode(), _policy())


def _assert_nothing(value: object) -> None:
    """Accept an observed value when a case targets another boundary."""
    # Explicit disposal documents that the callback is present only to satisfy
    # the public contract and must not influence the branch under test.
    del value


def _assert_type_error(action: Callable[[], object], message: str) -> None:
    """Require one setup action to fail with a precise type diagnostic."""
    try:
        action()
    except TypeError as error:
        assert str(error) == message
        return
    raise AssertionError("Expected contract setup to reject an invalid type.")


def _construct_incomplete_suite() -> object:
    """Attempt construction with a resolver missing required behavior."""
    # The cast crosses the static boundary deliberately so runtime structural
    # validation can reject the missing resolve member.
    return ModelIntegrationResolverContractSuite(
        cast(ModelIntegrationResolver, _IncompleteResolver())
    )


def _construct_invalid_descriptor_suite() -> object:
    """Attempt construction with malformed component metadata."""
    # This resolver has complete behavior, isolating descriptor validation from
    # structural protocol recognition.
    return ModelIntegrationResolverContractSuite(_InvalidDescriptorResolver())


def _construct_async_suite() -> object:
    """Attempt construction with an asynchronous resolve operation."""
    # Runtime protocol recognition accepts the member shape; constructor logic
    # must additionally enforce the synchronous execution contract.
    return ModelIntegrationResolverContractSuite(
        cast(ModelIntegrationResolver, _AsyncResolver())
    )


def test_suite_validates_exact_direct_plan_with_existing_stub() -> None:
    """Preserve the exact direct plan and its minimal provenance."""
    expected = _direct_plan()
    resolver = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )
    observed: list[ModelIntegrationPlan] = []

    def assert_plan(actual: ModelIntegrationPlan) -> None:
        """Require exact direct-plan identity and adapter ownership."""
        assert actual is expected
        assert actual.source == "direct_adapter"
        assert actual.binding_id is None
        assert actual.match is None
        assert actual.task_protocol_adapter is expected.task_protocol_adapter
        observed.append(actual)

    ModelIntegrationResolverContractSuite(resolver).assert_direct(
        *_inputs(),
        assertion=assert_plan,
    )

    assert observed == [expected]


def test_suite_validates_resolved_plan_and_preserves_all_inputs() -> None:
    """Invoke a structural resolver once with four exact input identities."""
    target, task, mode, policy = _inputs()
    expected = _resolved_plan()
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(expected, recorder)

    def assert_plan(actual: ModelIntegrationPlan) -> None:
        """Require exact resolved plan and complete binding provenance."""
        assert actual is expected
        assert actual.source == "resolved_binding"
        assert actual.binding_id == "binding.fixture.conversation"
        assert actual.match is expected.match
        assert actual.task_protocol_adapter is expected.task_protocol_adapter

    ModelIntegrationResolverContractSuite(resolver).assert_resolved(
        target,
        task,
        mode,
        policy,
        assertion=assert_plan,
    )

    assert recorder.calls == ("resolve_model_integration",)
    assert resolver.calls == ((target, task, mode, policy),)
    assert resolver.calls[0][0] is target
    assert resolver.calls[0][1] is task
    assert resolver.calls[0][2] is mode
    assert resolver.calls[0][3] is policy


def test_suite_validates_not_found_failure_without_fallback() -> None:
    """Expose the exact no-match failure instead of a fabricated plan."""
    failure = _resolution_error("unsupported_model_integration")
    resolver = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_plan(),
        error=failure,
    )
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require exact identity and stable unsupported-integration code."""
        assert actual is failure
        assert isinstance(actual, ModelInteractionError)
        assert actual.code == "unsupported_model_integration"
        observed.append(actual)

    ModelIntegrationResolverContractSuite(resolver).assert_not_found(
        *_inputs(),
        assertion=assert_failure,
    )

    assert observed == [failure]


def test_suite_validates_ambiguous_failure_without_order_selection() -> None:
    """Expose the exact ambiguity instead of choosing one candidate."""
    failure = _resolution_error("ambiguous_model_integration")
    resolver = StubModelIntegrationResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_plan(),
        error=failure,
    )

    def assert_failure(actual: BaseException) -> None:
        """Require exact identity and stable ambiguity code."""
        assert actual is failure
        assert isinstance(actual, ModelInteractionError)
        assert actual.code == "ambiguous_model_integration"

    ModelIntegrationResolverContractSuite(resolver).assert_ambiguous(
        *_inputs(),
        assertion=assert_failure,
    )


def test_success_cases_reject_wrong_source_and_malformed_result() -> None:
    """Keep direct and resolved provenance separate at the suite boundary."""
    direct_suite = ModelIntegrationResolverContractSuite(
        StubModelIntegrationResolver(
            ComponentDescriptor("Direct stub", "1", "application"),
            _direct_plan(),
        )
    )
    resolved_suite = ModelIntegrationResolverContractSuite(
        StubModelIntegrationResolver(
            ComponentDescriptor("Resolved stub", "1", "application"),
            _resolved_plan(),
        )
    )

    try:
        resolved_suite.assert_direct(*_inputs(), assertion=_assert_nothing)
    except AssertionError as error:
        assert str(error) == ("resolver must return a direct_adapter integration plan.")
    else:
        raise AssertionError("Expected resolved provenance in a direct case to fail.")

    try:
        direct_suite.assert_resolved(*_inputs(), assertion=_assert_nothing)
    except AssertionError as error:
        assert str(error) == (
            "resolver must return a resolved_binding integration plan."
        )
    else:
        raise AssertionError("Expected direct provenance in a resolved case to fail.")

    malformed_suite = ModelIntegrationResolverContractSuite(_MalformedResultResolver())
    try:
        malformed_suite.assert_resolved(*_inputs(), assertion=_assert_nothing)
    except AssertionError as error:
        assert str(error) == "resolver must return a ModelIntegrationPlan."
    else:
        raise AssertionError("Expected a malformed resolver result to fail.")


def test_failure_cases_reject_successful_fallback_plans() -> None:
    """Require both negative branches to fail rather than return any plan."""
    suite = ModelIntegrationResolverContractSuite(
        StubModelIntegrationResolver(
            ComponentDescriptor("Stub resolver", "1", "application"),
            _resolved_plan(),
        )
    )

    try:
        suite.assert_not_found(*_inputs(), assertion=_assert_nothing)
    except AssertionError as error:
        assert str(error) == (
            "resolver was expected to find no matching model integration."
        )
    else:
        raise AssertionError("Expected a not-found fallback plan to fail.")

    try:
        suite.assert_ambiguous(*_inputs(), assertion=_assert_nothing)
    except AssertionError as error:
        assert str(error) == (
            "resolver was expected to reject ambiguous model integrations."
        )
    else:
        raise AssertionError("Expected an ambiguous selected plan to fail.")


def test_suite_preserves_success_and_failure_callback_exceptions() -> None:
    """Propagate exact callback failures outside resolver control flow."""
    success_failure = RuntimeError("success assertion failed")
    resolution_failure = _resolution_error("unsupported_model_integration")
    failure_callback_error = RuntimeError("failure assertion failed")

    def fail_success_assertion(actual: ModelIntegrationPlan) -> None:
        """Raise one exact callback failure after observing a valid plan."""
        del actual
        raise success_failure

    def fail_failure_assertion(actual: BaseException) -> None:
        """Confirm the resolver failure, then raise an exact callback failure."""
        assert actual is resolution_failure
        raise failure_callback_error

    success_suite = ModelIntegrationResolverContractSuite(
        StubModelIntegrationResolver(
            ComponentDescriptor("Success stub", "1", "application"),
            _resolved_plan(),
        )
    )
    failure_suite = ModelIntegrationResolverContractSuite(
        StubModelIntegrationResolver(
            ComponentDescriptor("Failure stub", "1", "application"),
            _resolved_plan(),
            error=resolution_failure,
        )
    )

    try:
        success_suite.assert_resolved(*_inputs(), assertion=fail_success_assertion)
    except RuntimeError as error:
        assert error is success_failure
    else:
        raise AssertionError("Expected the success assertion callback to fail.")

    try:
        failure_suite.assert_not_found(
            *_inputs(),
            assertion=fail_failure_assertion,
        )
    except RuntimeError as error:
        assert error is failure_callback_error
        assert error is not resolution_failure
    else:
        raise AssertionError("Expected the failure assertion callback to fail.")


def test_suite_rejects_invalid_resolver_shapes_at_construction() -> None:
    """Reject incomplete, malformed-metadata, and asynchronous resolvers."""
    _assert_type_error(
        _construct_incomplete_suite,
        "resolver must implement ModelIntegrationResolver.",
    )
    _assert_type_error(
        _construct_invalid_descriptor_suite,
        "resolver descriptor must be a ComponentDescriptor.",
    )
    _assert_type_error(
        _construct_async_suite,
        "resolver operation must be synchronous.",
    )


def test_suite_validates_inputs_and_callback_before_resolution() -> None:
    """Reject malformed setup without invoking the resolver operation."""
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(_resolved_plan(), recorder)
    suite = ModelIntegrationResolverContractSuite(resolver)
    target, task, mode, policy = _inputs()

    try:
        suite.assert_resolved(
            cast(ModelTarget, object()),
            task,
            mode,
            policy,
            assertion=_assert_nothing,
        )
    except TypeError as error:
        assert str(error) == "target must implement ModelTarget."
    else:
        raise AssertionError("Expected an invalid target to fail before resolution.")

    try:
        suite.assert_resolved(
            target,
            cast(TaskDescriptor, object()),
            mode,
            policy,
            assertion=_assert_nothing,
        )
    except TypeError as error:
        assert str(error) == "descriptor must implement TaskDescriptor."
    else:
        raise AssertionError("Expected an invalid task to fail before resolution.")

    try:
        suite.assert_resolved(
            target,
            task,
            cast(InteractionMode, object()),
            policy,
            assertion=_assert_nothing,
        )
    except TypeError as error:
        assert str(error) == "mode must implement InteractionMode."
    else:
        raise AssertionError("Expected an invalid mode to fail before resolution.")

    try:
        suite.assert_resolved(
            target,
            task,
            mode,
            cast(CompatibilityPolicy, object()),
            assertion=_assert_nothing,
        )
    except TypeError as error:
        assert str(error) == "policy must be a CompatibilityPolicy."
    else:
        raise AssertionError("Expected an invalid policy to fail before resolution.")

    try:
        suite.assert_resolved(
            target,
            task,
            mode,
            policy,
            assertion=cast(Callable[[ModelIntegrationPlan], None], object()),
        )
    except TypeError as error:
        assert str(error) == "assertion must be callable."
    else:
        raise AssertionError("Expected a non-callable assertion to fail.")

    assert recorder.calls == ()
    assert resolver.calls == ()


def test_suite_rejects_async_assertion_before_resolution() -> None:
    """Prevent an unawaited assertion callback from crossing the sync API."""
    recorder = ComponentCallRecorder()
    resolver = _RecordingResolver(_resolved_plan(), recorder)

    async def assert_plan(actual: ModelIntegrationPlan) -> None:
        """Represent an invalid asynchronous assertion callback."""
        del actual

    try:
        ModelIntegrationResolverContractSuite(resolver).assert_resolved(
            *_inputs(),
            assertion=cast(Callable[[ModelIntegrationPlan], None], assert_plan),
        )
    except TypeError as error:
        assert str(error) == "assertion must be synchronous."
    else:
        raise AssertionError("Expected an async assertion to be rejected.")

    assert recorder.calls == ()


def test_suite_exposes_exact_synchronous_branch_surface() -> None:
    """Keep matching algorithms, registries, and execution stages out of scope."""
    suite = ModelIntegrationResolverContractSuite(
        StubModelIntegrationResolver(
            ComponentDescriptor("Stub resolver", "1", "application"),
            _resolved_plan(),
        )
    )
    expected_callback_types = {
        "assert_direct": Callable[[ModelIntegrationPlan], None],
        "assert_resolved": Callable[[ModelIntegrationPlan], None],
        "assert_not_found": Callable[[BaseException], None],
        "assert_ambiguous": Callable[[BaseException], None],
    }

    for name, callback_type in expected_callback_types.items():
        # Every branch consumes the same complete matching tuple and differs
        # only in the result or failure supplied to its assertion callback.
        operation = getattr(ModelIntegrationResolverContractSuite, name)
        signature = inspect.signature(operation)
        annotations = get_type_hints(operation)
        assert tuple(signature.parameters) == (
            "self",
            "target",
            "task",
            "mode",
            "policy",
            "assertion",
        )
        assert annotations == {
            "target": ModelTarget,
            "task": TaskDescriptor,
            "mode": InteractionMode,
            "policy": CompatibilityPolicy,
            "assertion": callback_type,
            "return": type(None),
        }
        assert not inspect.iscoroutinefunction(operation)

    for forbidden_member in (
        "register",
        "add",
        "remove",
        "match",
        "score",
        "lookup_component_id",
        "prepare_plan",
        "encode",
        "authorize",
        "send",
        "retry",
        "reset",
    ):
        assert not hasattr(suite, forbidden_member)
