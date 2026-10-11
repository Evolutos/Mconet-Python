"""Tests for direct-adapter integration plans and their precedence."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    Extensions,
    InteractionMode,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    ParsedTaskResponse,
    ResolvedServiceAccess,
    TaskDescriptor,
)
from mconet.core.runtime._direct_model_integration_plan import (
    direct_model_integration_plan,
    select_model_integration_plan,
)
from mconet.core.runtime._model_integration_resolution_errors import (
    UNSUPPORTED_MODEL_INTEGRATION_CODE,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    TaskProtocolAdapter,
    TransportResponseMetadata,
)

_POLICY = CompatibilityPolicy(OpenIdentifier("strict"))


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Task:
    """Complete structural task descriptor."""

    type: OpenIdentifier
    version: str | None = None
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Mode:
    """Structural interaction mode."""

    id: OpenIdentifier


class _Adapter:
    """Adapter stub answering supports with a configured value."""

    def __init__(self, answer: object) -> None:
        """Store the supports answer and an empty call log."""
        self._answer = answer
        self.calls: list[tuple[object, object, object]] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return fixed application metadata."""
        return ComponentDescriptor("direct-adapter", "1.0.0", "application")

    def supports(
        self, target: ModelTarget, task: TaskDescriptor, mode: InteractionMode
    ) -> bool:
        """Record the exact inputs and return the configured answer."""
        self.calls.append((target, task, mode))
        return cast(bool, self._answer)

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: InteractionMode,
    ) -> ProtocolExecutionPlan:
        """Fail because planning is not part of integration resolution."""
        raise AssertionError("prepare_plan must not be called.")

    def build_request(
        self, request: ModelRequest, plan: ProtocolExecutionPlan
    ) -> ProtocolRequestPlan:
        """Fail because request building is not part of resolution."""
        raise AssertionError("build_request must not be called.")

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Fail because parsing is not part of resolution."""
        raise AssertionError("parse_response must not be called.")

    def parse_error(
        self, error: ErasedRuntimeValue, metadata: TransportResponseMetadata
    ) -> ModelInteractionError | None:
        """Fail because parsing is not part of resolution."""
        raise AssertionError("parse_error must not be called.")


class _Resolver:
    """Resolver stub recording calls and returning a configured plan."""

    def __init__(self, plan: ModelIntegrationPlan | None) -> None:
        """Store the plan to return, or None to fail when called."""
        self._plan = plan
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
        """Return the configured plan, or fail when none was configured."""
        del target, task, mode, policy
        self.calls += 1
        if self._plan is None:
            raise AssertionError("resolve must not be called.")
        return self._plan


def _inputs() -> tuple[_Target, _Task, _Mode]:
    """Return one request for a protocol no resolver knows."""
    return (
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier("vendor.unknown-protocol"),
            NamedModel("m-1"),
        ),
        _Task(OpenIdentifier("conversation.generate")),
        _Mode(OpenIdentifier("unary")),
    )


def test_supported_adapter_gets_a_minimal_direct_plan() -> None:
    """Verify the plan holds only the adapter, after asking supports."""
    adapter = _Adapter(True)
    target, task, mode = _inputs()

    plan = direct_model_integration_plan(adapter, target, task, mode)

    assert isinstance(adapter, TaskProtocolAdapter)
    assert plan.source == "direct_adapter"
    assert plan.task_protocol_adapter is adapter
    assert plan.binding_id is None
    assert plan.binding_version is None
    assert plan.match is None
    assert plan.authorization_handlers == ()
    assert plan.default_service_access is None
    assert plan.payload_encoders == ()
    assert plan.payload_decoders == ()
    assert plan.transports == ()
    assert len(adapter.calls) == 1
    assert adapter.calls[0][0] is target
    assert adapter.calls[0][1] is task
    assert adapter.calls[0][2] is mode


def test_unsupporting_adapter_fails_immediately() -> None:
    """Verify an injected adapter that rejects the request is never used."""
    adapter = _Adapter(False)

    error = _capture(lambda: direct_model_integration_plan(adapter, *_inputs()))

    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "unsupported_feature"
    assert error.phase.id.value == "model_integration_resolution"
    assert error.code == UNSUPPORTED_MODEL_INTEGRATION_CODE
    assert error.message == (
        "The injected task protocol adapter does not support the target, task, "
        "and mode."
    )


def test_supports_must_return_an_exact_bool() -> None:
    """Verify a truthy or falsy placeholder is not taken as an answer."""
    for answer in (1, "yes", None, 0):
        error = _capture(
            lambda answer=answer: direct_model_integration_plan(
                _Adapter(answer), *_inputs()
            )
        )

        assert isinstance(error, TypeError)


def test_direct_plan_rejects_an_object_that_is_not_an_adapter() -> None:
    """Verify only a complete TaskProtocolAdapter can be injected."""
    error = _capture(
        lambda: direct_model_integration_plan(
            cast(TaskProtocolAdapter, object()), *_inputs()
        )
    )

    assert isinstance(error, TypeError)


def test_injected_adapter_bypasses_the_resolver_completely() -> None:
    """Verify the resolver is never called, even for an unknown protocol."""
    adapter = _Adapter(True)
    resolver = _Resolver(None)

    plan = select_model_integration_plan(adapter, resolver, *_inputs(), _POLICY)

    assert plan.task_protocol_adapter is adapter
    assert resolver.calls == 0


def test_rejecting_injected_adapter_does_not_fall_back_to_the_resolver() -> None:
    """Verify an explicit adapter's refusal is final."""
    resolver = _Resolver(None)

    error = _capture(
        lambda: select_model_integration_plan(
            _Adapter(False), resolver, *_inputs(), _POLICY
        )
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == UNSUPPORTED_MODEL_INTEGRATION_CODE
    assert resolver.calls == 0


def test_without_an_injected_adapter_the_resolver_decides() -> None:
    """Verify the resolver's plan is returned unchanged."""
    resolved = ModelIntegrationPlan(
        source="direct_adapter",
        binding_id=None,
        binding_version=None,
        match=None,
        task_protocol_adapter=_Adapter(True),
    )
    resolver = _Resolver(resolved)

    plan = select_model_integration_plan(None, resolver, *_inputs(), _POLICY)

    assert isinstance(resolver, ModelIntegrationResolver)
    assert plan is resolved
    assert resolver.calls == 1
    error = _capture(
        lambda: select_model_integration_plan(
            None, cast(ModelIntegrationResolver, object()), *_inputs(), _POLICY
        )
    )
    assert isinstance(error, TypeError)
