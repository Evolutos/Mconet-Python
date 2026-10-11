"""Tests for the default type-table and chain model integration resolver."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    Extensions,
    InteractionMode,
    ModelDescriptor,
    ModelInteractionError,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.runtime._integration_responsibility_chain import (
    IntegrationResponsibilityChain,
)
from mconet.core.runtime._integration_type_key import IntegrationTypeKey
from mconet.core.runtime._integration_type_table import IntegrationTypeTable
from mconet.core.runtime._model_integration_binding import ModelIntegrationBinding
from mconet.core.runtime._model_integration_resolution_errors import (
    UNSUPPORTED_MODEL_INTEGRATION_CODE,
)
from mconet.core.runtime.default_model_integration_resolver import (
    DEFAULT_MODEL_INTEGRATION_RESOLVER_DESCRIPTOR,
    DefaultModelIntegrationResolver,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelIntegrationPlan,
    ModelIntegrationResolver,
    ModelTargetMatch,
    TaskMatch,
)
from mconet.testing.model_integration_resolver_contract_suite import (
    ModelIntegrationResolverContractSuite,
)

_PROTOCOL = "vendor.chat"
_TASK = OpenIdentifier("conversation.generate")
_UNARY = OpenIdentifier("unary")
_STRICT = CompatibilityPolicy(OpenIdentifier("strict"))
_COMPATIBLE = CompatibilityPolicy(OpenIdentifier("compatible"))
_PERMISSIVE = CompatibilityPolicy(OpenIdentifier("permissive"))
_FUTURE = CompatibilityPolicy(OpenIdentifier("vendor.future"))


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


@dataclass(frozen=True, slots=True)
class _Component:
    """Runtime component carrying only descriptor metadata."""

    descriptor: ComponentDescriptor


class _ServiceMatcher:
    """Target matcher accepting one service, or any service when unset."""

    def __init__(self, service: str | None, score: int) -> None:
        """Store the accepted service and the score to report."""
        self._service = None if service is None else OpenIdentifier(service)
        self._score = score

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Accept the configured service only."""
        if self._service is not None and target.service_id != self._service:
            return None
        return ModelTargetMatch(True, self._score)


class _AnyTask:
    """Task matcher accepting every task and mode."""

    def match(self, task: TaskDescriptor, mode: InteractionMode) -> TaskMatch | None:
        """Accept the request with a fixed score."""
        del task, mode
        return TaskMatch(True, 2)


def _component(name: str) -> _Component:
    """Build one distinguishable component."""
    return _Component(ComponentDescriptor(name, "1.0.0", "plugin"))


def _binding(
    name: str, service: str | None = None, score: int = 1
) -> ModelIntegrationBinding:
    """Build a complete binding with one instance in every role."""
    return ModelIntegrationBinding(
        id=name,
        version="2.1.0",
        target_matcher=_ServiceMatcher(service, score),
        task_matcher=_AnyTask(),
        task_protocol_adapter=_component(f"{name}-adapter"),
        authorization_handlers=(_component(f"{name}-auth"),),
        default_service_access=None,
        payload_encoders=(_component(f"{name}-encoder"),),
        payload_decoders=(_component(f"{name}-decoder"),),
        transports=(_component(f"{name}-transport"),),
        extensions={"internal": object()},
    )


def _key(protocol: str = _PROTOCOL) -> IntegrationTypeKey:
    """Build the conversation unary key of one protocol."""
    return IntegrationTypeKey(OpenIdentifier(protocol), _TASK, _UNARY)


def _resolver(
    table: tuple[tuple[IntegrationTypeKey, ModelIntegrationBinding], ...] = (),
    chain: tuple[ModelIntegrationBinding, ...] = (),
) -> DefaultModelIntegrationResolver:
    """Build a resolver from table entries and chain bindings."""
    return DefaultModelIntegrationResolver(
        IntegrationTypeTable(table), IntegrationResponsibilityChain(chain)
    )


def _inputs(
    protocol: str = _PROTOCOL, service: str = "service.vendor"
) -> tuple[_Target, _Task, _Mode]:
    """Return one complete request."""
    return (
        _Target(OpenIdentifier(service), OpenIdentifier(protocol), NamedModel("m-1")),
        _Task(_TASK),
        _Mode(_UNARY),
    )


def _assert_unsupported(error: BaseException) -> None:
    """Assert the stable no-match failure."""
    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "unsupported_feature"
    assert error.phase.id.value == "model_integration_resolution"
    assert error.code == UNSUPPORTED_MODEL_INTEGRATION_CODE
    assert error.message == "No model integration supports the target, task, and mode."


def test_resolver_is_a_runtime_model_integration_resolver() -> None:
    """Verify the resolver satisfies the SPI and has fixed metadata."""
    resolver: ModelIntegrationResolver = _resolver()

    assert isinstance(resolver, ModelIntegrationResolver)
    assert resolver.descriptor is DEFAULT_MODEL_INTEGRATION_RESOLVER_DESCRIPTOR
    for name in ("register", "add", "remove"):
        assert not hasattr(resolver, name)


def test_exact_table_hit_returns_a_complete_binding_snapshot() -> None:
    """Verify the plan keeps provenance, match facts, and instances in order."""
    binding = _binding("table", score=7)
    resolver = _resolver(((_key(), binding),))

    def check(plan: ModelIntegrationPlan) -> None:
        assert plan.binding_id == "table"
        assert plan.binding_version == "2.1.0"
        assert plan.match == ModelIntegrationMatch(
            ModelTargetMatch(True, 7), TaskMatch(True, 2)
        )
        assert plan.task_protocol_adapter is binding.task_protocol_adapter
        assert plan.authorization_handlers == binding.authorization_handlers
        assert plan.authorization_handlers[0] is binding.authorization_handlers[0]
        assert plan.default_service_access is None
        assert plan.payload_encoders[0] is binding.payload_encoders[0]
        assert plan.payload_decoders[0] is binding.payload_decoders[0]
        assert plan.transports[0] is binding.transports[0]
        assert dict(plan.extensions) == {}

    suite = ModelIntegrationResolverContractSuite(resolver)
    for policy in (_STRICT, _COMPATIBLE, _PERMISSIVE, _FUTURE):
        suite.assert_resolved(*_inputs(), policy, assertion=check)


def test_table_takes_precedence_over_the_chain() -> None:
    """Verify an exact key wins even over an earlier-declared chain match."""
    table_binding = _binding("table")
    resolver = _resolver(((_key(), table_binding),), (_binding("chain"),))

    plan = resolver.resolve(*_inputs(), _COMPATIBLE)

    assert plan.binding_id == "table"


def test_strict_and_unknown_policies_never_use_the_chain() -> None:
    """Verify fail-closed modes report no match instead of a chain binding."""
    resolver = _resolver(chain=(_binding("chain"),))
    suite = ModelIntegrationResolverContractSuite(resolver)

    for policy in (_STRICT, _FUTURE):
        suite.assert_not_found(*_inputs(), policy, assertion=_assert_unsupported)


def test_relaxed_policies_use_the_first_applicable_chain_binding() -> None:
    """Verify compatible and permissive fall back to declared chain rules."""
    resolver = _resolver(
        chain=(_binding("other", service="service.other"), _binding("generic"))
    )

    for policy in (_COMPATIBLE, _PERMISSIVE):
        plan = resolver.resolve(*_inputs(), policy)

        assert plan.source == "resolved_binding"
        assert plan.binding_id == "generic"


def test_a_table_binding_whose_matchers_reject_falls_through() -> None:
    """Verify a key hit still needs the binding's own matchers to accept."""
    resolver = _resolver(
        ((_key(), _binding("table", service="service.other")),),
        (_binding("chain"),),
    )

    assert resolver.resolve(*_inputs(), _COMPATIBLE).binding_id == "chain"
    _assert_unsupported(_capture(lambda: resolver.resolve(*_inputs(), _STRICT)))


def test_no_applicable_entry_raises_unsupported_model_integration() -> None:
    """Verify an unknown protocol, task, or mode has no fallback plan."""
    resolver = _resolver(((_key(), _binding("table")),))
    suite = ModelIntegrationResolverContractSuite(resolver)
    target, task, _ = _inputs()

    suite.assert_not_found(
        *_inputs(protocol="vendor.other"), _COMPATIBLE, assertion=_assert_unsupported
    )
    suite.assert_not_found(
        target,
        _Task(OpenIdentifier("embedding.create")),
        _Mode(_UNARY),
        _COMPATIBLE,
        assertion=_assert_unsupported,
    )
    suite.assert_not_found(
        target,
        task,
        _Mode(OpenIdentifier("server_stream")),
        _COMPATIBLE,
        assertion=_assert_unsupported,
    )
    _assert_unsupported(_capture(lambda: _resolver().resolve(*_inputs(), _COMPATIBLE)))


def test_resolver_rejects_malformed_parts_and_policy() -> None:
    """Verify construction and resolution check their argument types."""
    table = IntegrationTypeTable(())
    chain = IntegrationResponsibilityChain(())
    for action in (
        lambda: DefaultModelIntegrationResolver(cast(IntegrationTypeTable, ()), chain),
        lambda: DefaultModelIntegrationResolver(
            table, cast(IntegrationResponsibilityChain, ())
        ),
        lambda: _resolver().resolve(
            *_inputs(), cast(CompatibilityPolicy, "compatible")
        ),
    ):
        assert isinstance(_capture(action), TypeError)
