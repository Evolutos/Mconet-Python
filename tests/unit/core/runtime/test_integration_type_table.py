"""Tests for the immutable exact-key integration type table."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import (
    InteractionMode,
    ModelInteractionError,
    ModelTarget,
    OpenIdentifier,
    TaskDescriptor,
)
from mconet.core.runtime._integration_type_key import IntegrationTypeKey
from mconet.core.runtime._integration_type_table import IntegrationTypeTable
from mconet.core.runtime._model_integration_binding import ModelIntegrationBinding
from mconet.core.runtime._model_integration_resolution_errors import (
    AMBIGUOUS_MODEL_INTEGRATION_CODE,
)
from mconet.core.spi import ComponentDescriptor, ModelTargetMatch, TaskMatch


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Runtime component carrying only descriptor metadata."""

    descriptor: ComponentDescriptor


class _TargetMatcher:
    """Target matcher that must not be consulted by table lookup."""

    def match(self, target: ModelTarget) -> ModelTargetMatch | None:
        """Fail because lookup is by key only."""
        del target
        raise AssertionError("Table lookup must not run matchers.")


class _TaskMatcher:
    """Task matcher that must not be consulted by table lookup."""

    def match(self, task: TaskDescriptor, mode: InteractionMode) -> TaskMatch | None:
        """Fail because lookup is by key only."""
        del task, mode
        raise AssertionError("Table lookup must not run matchers.")


def _binding(binding_id: str) -> ModelIntegrationBinding:
    """Build one distinguishable binding."""
    return ModelIntegrationBinding(
        id=binding_id,
        version="1.0.0",
        target_matcher=_TargetMatcher(),
        task_matcher=_TaskMatcher(),
        task_protocol_adapter=_Component(
            ComponentDescriptor(f"{binding_id}-adapter", "1.0.0", "plugin")
        ),
        authorization_handlers=(),
        default_service_access=None,
        payload_encoders=(),
        payload_decoders=(),
        transports=(),
    )


def _key(protocol: str, mode: str = "unary") -> IntegrationTypeKey:
    """Build a conversation key for one protocol and mode."""
    return IntegrationTypeKey(
        OpenIdentifier(protocol),
        OpenIdentifier("conversation.generate"),
        OpenIdentifier(mode),
    )


def test_exact_lookup_returns_the_unique_binding_by_identity() -> None:
    """Verify each key returns its own binding and one binding may repeat."""
    first = _binding("first")
    second = _binding("second")
    table = IntegrationTypeTable(
        (
            (_key("vendor.a"), first),
            (_key("vendor.a", "server_stream"), first),
            (_key("vendor.b"), second),
        )
    )

    assert table.lookup(_key("vendor.a")) is first
    assert table.lookup(_key("vendor.a", "server_stream")) is first
    assert table.lookup(_key("vendor.b")) is second


def test_lookup_has_no_partial_or_fallback_match() -> None:
    """Verify a key differing in any part finds nothing."""
    table = IntegrationTypeTable(((_key("vendor.a"), _binding("first")),))
    misses = (
        _key("vendor.a", "duplex"),
        _key("vendor"),
        _key("vendor.a.v2"),
        IntegrationTypeKey(
            OpenIdentifier("vendor.a"),
            OpenIdentifier("embedding.create"),
            OpenIdentifier("unary"),
        ),
    )

    for key in misses:
        assert table.lookup(key) is None
    assert IntegrationTypeTable(()).lookup(_key("vendor.a")) is None


def test_keys_keep_declaration_order() -> None:
    """Verify diagnostics see the assembly order."""
    keys = (_key("vendor.z"), _key("vendor.a"), _key("vendor.m"))
    table = IntegrationTypeTable(
        tuple((key, _binding(key.serialize())) for key in keys)
    )

    assert table.keys == keys


def test_duplicate_keys_fail_at_construction() -> None:
    """Verify a repeated key is ambiguous even with the same binding."""
    binding = _binding("first")
    for duplicate in (binding, _binding("second")):
        error = _capture(
            lambda duplicate=duplicate: IntegrationTypeTable(
                ((_key("vendor.a"), binding), (_key("vendor.a"), duplicate))
            )
        )

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "invalid_component_configuration"
        assert error.phase.id.value == "model_integration_resolution"
        assert error.code == AMBIGUOUS_MODEL_INTEGRATION_CODE


def test_table_is_immutable_after_construction() -> None:
    """Verify neither the caller tuple nor the table can change membership."""
    binding = _binding("first")
    entries = ((_key("vendor.a"), binding),)
    table = IntegrationTypeTable(entries)

    assert not hasattr(table, "register")
    assert not hasattr(table, "add")
    assert not hasattr(table, "remove")
    error = _capture(lambda: setattr(table, "extra", 1))
    assert isinstance(error, AttributeError)
    assert isinstance(table.keys, tuple)
    assert table.lookup(_key("vendor.a")) is binding


def test_table_rejects_malformed_entries() -> None:
    """Verify containers and pair members have precise types."""
    binding = _binding("first")
    cases: tuple[object, ...] = (
        [(_key("vendor.a"), binding)],
        (("vendor.a", binding),),
        ((_key("vendor.a"), object()),),
        ((_key("vendor.a"),),),
        ([_key("vendor.a"), binding],),
    )
    for entries in cases:
        error = _capture(
            lambda entries=entries: IntegrationTypeTable(
                cast(
                    tuple[tuple[IntegrationTypeKey, ModelIntegrationBinding], ...],
                    entries,
                )
            )
        )

        assert isinstance(error, TypeError)
