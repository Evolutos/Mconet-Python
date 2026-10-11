"""Tests for the explicit ordered integration responsibility chain."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
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
from mconet.core.runtime._model_integration_binding import ModelIntegrationBinding
from mconet.core.runtime._model_integration_resolution_errors import (
    AMBIGUOUS_MODEL_INTEGRATION_CODE,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ModelIntegrationMatch,
    ModelTargetMatch,
    TaskMatch,
)


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


class _ProtocolMatcher:
    """Target matcher accepting one protocol with a fixed score."""

    def __init__(self, protocol: str, score: int, calls: list[str], name: str) -> None:
        """Store the accepted protocol, score, and shared call log."""
        self._protocol = OpenIdentifier(protocol)
        self._score = score
        self._calls = calls
        self._name = name

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Record the call and accept only the configured protocol."""
        self._calls.append(self._name)
        if target.protocol_id != self._protocol:
            return None
        return ModelTargetMatch(True, self._score)


class _AnyTask:
    """Task matcher accepting every task and mode."""

    def match(self, task: TaskDescriptor, mode: InteractionMode) -> TaskMatch | None:
        """Accept the request with a fixed score."""
        del task, mode
        return TaskMatch(True, 1)


def _binding(
    name: str, protocol: str, calls: list[str], score: int = 1
) -> ModelIntegrationBinding:
    """Build one binding accepting a single protocol."""
    return ModelIntegrationBinding(
        id=name,
        version="1.0.0",
        target_matcher=_ProtocolMatcher(protocol, score, calls, name),
        task_matcher=_AnyTask(),
        task_protocol_adapter=_Component(
            ComponentDescriptor(f"{name}-adapter", "1.0.0", "plugin")
        ),
        authorization_handlers=(),
        default_service_access=None,
        payload_encoders=(),
        payload_decoders=(),
        transports=(),
    )


def _inputs(protocol: str) -> tuple[_Target, _Task, _Mode]:
    """Return one request for the given protocol."""
    return (
        _Target(
            OpenIdentifier("service.vendor"),
            OpenIdentifier(protocol),
            NamedModel("fixture-model"),
        ),
        _Task(OpenIdentifier("conversation.generate")),
        _Mode(OpenIdentifier("unary")),
    )


def test_first_applicable_binding_wins_and_later_ones_are_not_asked() -> None:
    """Verify declaration order decides and evaluation stops at the winner."""
    calls: list[str] = []
    first = _binding("first", "vendor.a", calls, score=1)
    second = _binding("second", "vendor.b", calls, score=1)
    third = _binding("third", "vendor.b", calls, score=100)
    chain = IntegrationResponsibilityChain((first, second, third))

    result = chain.first_match(*_inputs("vendor.b"))

    assert result is not None
    binding, match = result
    assert binding is second
    assert match == ModelIntegrationMatch(ModelTargetMatch(True, 1), TaskMatch(True, 1))
    assert calls == ["first", "second"]


def test_scores_never_reorder_the_chain() -> None:
    """Verify a higher later score does not beat an earlier match."""
    calls: list[str] = []
    low = _binding("low", "vendor.a", calls, score=0)
    high = _binding("high", "vendor.a", calls, score=1000)

    result = IntegrationResponsibilityChain((low, high)).first_match(
        *_inputs("vendor.a")
    )

    assert result is not None
    assert result[0] is low


def test_no_applicable_binding_returns_none_after_asking_every_entry() -> None:
    """Verify every entry is asked in order before reporting no match."""
    calls: list[str] = []
    chain = IntegrationResponsibilityChain(
        (_binding("a", "vendor.a", calls), _binding("b", "vendor.b", calls))
    )

    assert chain.first_match(*_inputs("vendor.c")) is None
    assert calls == ["a", "b"]
    assert IntegrationResponsibilityChain(()).first_match(*_inputs("vendor.c")) is None


def test_binding_ids_expose_the_fixed_order() -> None:
    """Verify diagnostics can name the evaluation order."""
    calls: list[str] = []
    chain = IntegrationResponsibilityChain(
        (_binding("z", "vendor.a", calls), _binding("a", "vendor.b", calls))
    )

    assert chain.binding_ids == ("z", "a")


def test_repeated_binding_ids_fail_at_construction() -> None:
    """Verify an undiagnosable order is ambiguous before any request."""
    calls: list[str] = []
    binding = _binding("same", "vendor.a", calls)
    for duplicate in (binding, _binding("same", "vendor.b", calls)):
        error = _capture(
            lambda duplicate=duplicate: IntegrationResponsibilityChain(
                (binding, duplicate)
            )
        )

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "invalid_component_configuration"
        assert error.phase.id.value == "model_integration_resolution"
        assert error.code == AMBIGUOUS_MODEL_INTEGRATION_CODE
    assert calls == []


def test_chain_rejects_malformed_bindings_and_has_no_registration() -> None:
    """Verify the container is a tuple of bindings and cannot change."""
    calls: list[str] = []
    binding = _binding("a", "vendor.a", calls)
    for bindings in ([binding], (binding, object())):
        error = _capture(
            lambda bindings=bindings: IntegrationResponsibilityChain(
                cast(tuple[ModelIntegrationBinding, ...], bindings)
            )
        )

        assert isinstance(error, TypeError)

    chain = IntegrationResponsibilityChain((binding,))
    for name in ("register", "add", "remove", "append"):
        assert not hasattr(chain, name)
    assert isinstance(_capture(lambda: setattr(chain, "extra", 1)), AttributeError)
