"""Lifecycle validation for components stored on a reusable client."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.core.runtime._runtime_components_lifecycle_validation import (
    validate_runtime_components_lifecycle,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentOwnership,
    PayloadEncoder,
    RuntimeComponents,
    Transport,
)

_APPLICATION = ComponentOwnership(OpenIdentifier("application"))
_BUILTIN = ComponentOwnership(OpenIdentifier("builtin"))


class _Reusable:
    """Stateless component whose behavior must stay idle."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("encoder", "1.0.0", "application")
        self.calls: list[str] = []

    def encode(self, payload: object) -> object:
        """Record an encode call that validation must not make."""
        del payload
        self.calls.append("encode")
        return None


class _Resource:
    """Resource component with the asynchronous close contract."""

    def __init__(self, source: str = "builtin") -> None:
        """Store metadata that must not be read as ownership."""
        self.descriptor = ComponentDescriptor(
            "transport",
            "1.0.0",
            "builtin" if source == "builtin" else "application",
        )
        self.calls: list[str] = []

    async def close(self) -> None:
        """Record a close call that validation must not make."""
        self.calls.append("close")

    async def send(self, *values: object) -> object:
        """Record a send call that validation must not make."""
        del values
        self.calls.append("send")
        return None


class _SyncClose:
    """Component whose close is synchronous and therefore illegal."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("transport", "1.0.0", "application")
        self.calls: list[str] = []

    def close(self) -> None:
        """Record a close call that validation must not make."""
        self.calls.append("close")


class _Framer:
    """Per-interaction state instance that must not be stored on a client."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("framer", "1.0.0", "application")
        self.calls: list[str] = []

    def frame(self, data: object) -> object:
        """Record a frame call that validation must not make."""
        del data
        self.calls.append("frame")
        return None


class _Accumulator:
    """Per-interaction accumulator instance without a factory."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("accumulator", "1.0.0", "application")
        self.calls: list[str] = []

    def append(self, element: object) -> None:
        """Record an append call that validation must not make."""
        del element
        self.calls.append("append")

    def finalize(self) -> object:
        """Record a finalize call that validation must not make."""
        self.calls.append("finalize")
        return None


class _Factory:
    """State factory with no reusable behavior operation."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("factory", "1.0.0", "application")
        self.calls: list[str] = []

    def create(self, context: object) -> object:
        """Record a create call that validation must not make."""
        del context
        self.calls.append("create")
        return None


def _expect(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _assert_lifecycle(error: BaseException) -> None:
    """Require the stable lifecycle failure."""
    assert isinstance(error, ModelInteractionError)
    assert error.code == "invalid_component_lifecycle"
    assert str(error.phase.id) == "component_lifecycle"
    assert str(error.category.id) == "invalid_component_configuration"


def test_reusable_instance_is_kept_for_either_standard_owner() -> None:
    """Accept a stateless component without calling it."""
    component = _Reusable()
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, component))
    assert validate_runtime_components_lifecycle(components, _APPLICATION) is components
    assert validate_runtime_components_lifecycle(components, _BUILTIN) is components
    assert component.calls == []


def test_resource_component_keeps_the_supplied_owner() -> None:
    """Accept an asynchronous resource for builtin and application owners."""
    component = _Resource(source="builtin")
    components = RuntimeComponents(transport=cast(Transport, component))
    assert validate_runtime_components_lifecycle(components, _APPLICATION) is components
    assert validate_runtime_components_lifecycle(components, _BUILTIN) is components
    assert component.calls == []
    assert component.descriptor.source == "builtin"


def test_unknown_owner_fails_before_component_behavior() -> None:
    """Reject an owner the lifecycle rules cannot close or retain."""
    component = _Reusable()
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, component))
    error = _expect(
        ModelInteractionError,
        lambda: validate_runtime_components_lifecycle(
            components,
            ComponentOwnership(OpenIdentifier("plugin")),
        ),
        "Component lifecycle owner must be builtin or application.",
    )
    _assert_lifecycle(error)
    assert component.calls == []


def test_synchronous_close_is_rejected() -> None:
    """Reject a resource operation that is not the asynchronous contract."""
    component = _SyncClose()
    components = RuntimeComponents(transport=cast(Transport, component))
    error = _expect(
        ModelInteractionError,
        lambda: validate_runtime_components_lifecycle(components, _APPLICATION),
        "Component close must be an asynchronous lifecycle operation.",
    )
    _assert_lifecycle(error)
    assert component.calls == []


def test_interaction_state_instance_is_rejected() -> None:
    """Reject a framer or accumulator instance stored on the client."""
    framer = _Framer()
    accumulator = _Accumulator()
    framer_components = RuntimeComponents(transport=cast(Transport, framer))
    accumulator_components = RuntimeComponents(
        payload_encoder=cast(PayloadEncoder, accumulator)
    )
    framer_error = _expect(
        ModelInteractionError,
        lambda: validate_runtime_components_lifecycle(framer_components, _BUILTIN),
        "A stateful instance cannot be stored in client components.",
    )
    accumulator_error = _expect(
        ModelInteractionError,
        lambda: validate_runtime_components_lifecycle(
            accumulator_components, _APPLICATION
        ),
        "A stateful instance cannot be stored in client components.",
    )
    _assert_lifecycle(framer_error)
    _assert_lifecycle(accumulator_error)
    assert framer.calls == accumulator.calls == []


def test_state_factory_cannot_occupy_an_instance_field() -> None:
    """Reject a factory stored where R1 keeps a reusable instance."""
    factory = _Factory()
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, factory))
    error = _expect(
        ModelInteractionError,
        lambda: validate_runtime_components_lifecycle(components, _APPLICATION),
        "A stateful factory cannot occupy a reusable instance field.",
    )
    _assert_lifecycle(error)
    assert factory.calls == []


def test_reusable_helper_named_create_stays_an_instance() -> None:
    """Keep an encoder that exposes an unrelated create helper."""

    class _EncoderWithHelper(_Reusable):
        """Reusable encoder with a helper that is not a state factory."""

        def create(self, context: object) -> object:
            """Record a helper call that validation must not make."""
            del context
            self.calls.append("create")
            return None

    component = _EncoderWithHelper()
    components = RuntimeComponents(payload_encoder=cast(PayloadEncoder, component))
    assert validate_runtime_components_lifecycle(components, _APPLICATION) is components
    assert component.calls == []


def test_non_carrier_and_non_owner_are_rejected() -> None:
    """Reject values that are not the lifecycle carrier or owner."""
    _expect(
        TypeError,
        lambda: validate_runtime_components_lifecycle(
            cast(RuntimeComponents, object()),
            _APPLICATION,
        ),
        "components must be a RuntimeComponents",
    )
    _expect(
        TypeError,
        lambda: validate_runtime_components_lifecycle(
            RuntimeComponents(),
            cast(ComponentOwnership, object()),
        ),
        "owner must be a ComponentOwnership",
    )
