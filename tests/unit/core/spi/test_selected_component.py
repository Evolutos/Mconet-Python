"""Combination and boundary tests for selected runtime component snapshots."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import ComponentDescriptor, ComponentRole, SelectedComponent


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match field-specific wording so a fixture or protocol-access failure
        # cannot make a negative selected-component test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Application-defined component satisfying the structural SPI boundary."""

    descriptor: ComponentDescriptor
    """Immutable metadata exposed directly to component selection."""


@dataclass(frozen=True, slots=True)
class _UndescribedComponent:
    """Object intentionally lacking the required runtime component metadata."""

    name: str
    """Unrelated diagnostic label that cannot substitute for a descriptor."""


@dataclass(frozen=True, slots=True)
class _MalformedComponent:
    """Object with a descriptor-shaped field carrying the wrong value type."""

    descriptor: object
    """Invalid metadata used to exercise runtime boundary validation."""


def _role(value: str = "payload.encoder") -> ComponentRole:
    """Build one validated execution role for selection fixtures."""
    # Use the public open identifier path so fixtures follow production role
    # syntax instead of bypassing validation with a test-only substitute.
    return ComponentRole(OpenIdentifier(value))


def _descriptor(name: str = "JSON Encoder") -> ComponentDescriptor:
    """Build immutable application component metadata for selection fixtures."""
    # A minimal descriptor is enough because this value tests role association,
    # not the separate port-contract or capability selection rules.
    return ComponentDescriptor(name, "1.0", "application")


def test_selected_component_preserves_complete_selection_snapshot() -> None:
    """Verify role, component, and descriptor remain the exact selected values."""
    role = _role()
    descriptor = _descriptor()
    component = _Component(descriptor)

    selected = SelectedComponent(role, component, descriptor)

    # Identity preservation ensures later type and capability checks inspect the
    # same component instance and immutable metadata used during resolution.
    assert selected.role is role
    assert selected.component is component
    assert selected.descriptor is descriptor


def test_selected_component_accepts_equivalent_computed_metadata() -> None:
    """Verify descriptor consistency is value-based rather than identity-based."""
    component_descriptor = _descriptor()
    snapshot_descriptor = _descriptor()
    component = _Component(component_descriptor)

    selected = SelectedComponent(_role(), component, snapshot_descriptor)

    # Component implementations may compute a fresh immutable descriptor; equal
    # metadata still represents the same verified selection-time facts.
    assert component_descriptor is not snapshot_descriptor
    assert selected.descriptor is snapshot_descriptor


def test_selected_component_is_an_immutable_three_field_snapshot() -> None:
    """Verify the selection stores no registry identity or mutable metadata."""
    descriptor = _descriptor()
    selected = SelectedComponent(_role(), _Component(descriptor), descriptor)

    # The exact architecture surface excludes selection IDs, serialization data,
    # ownership state, and lifecycle hooks from this internal snapshot value.
    assert tuple(field.name for field in fields(SelectedComponent)) == (
        "role",
        "component",
        "descriptor",
    )
    assert not hasattr(selected, "id")
    assert not hasattr(selected, "component_id")
    assert not hasattr(selected, "close")
    _assert_raises(
        FrozenInstanceError,
        lambda: selected.__setattr__("role", _role("transport")),
        "cannot assign to field",
    )


def test_selected_component_requires_component_role() -> None:
    """Verify a string or bare identifier cannot replace role identity."""
    descriptor = _descriptor()
    component = _Component(descriptor)
    invalid_roles: tuple[object, ...] = (
        "payload.encoder",
        OpenIdentifier("payload.encoder"),
        object(),
    )

    # Validate every role before component inspection so callers receive a
    # deterministic error for the first invalid field in architecture order.
    for role in invalid_roles:
        _assert_raises(
            TypeError,
            lambda role=role: SelectedComponent(
                cast(ComponentRole, role), component, descriptor
            ),
            "role must be a ComponentRole",
        )


def test_selected_component_requires_runtime_component_protocol() -> None:
    """Verify unrelated objects cannot enter an execution component snapshot."""
    descriptor = _descriptor()

    # A component name or arbitrary object cannot replace the structural
    # descriptor property that Core uses for compatibility and capability checks.
    invalid_components: tuple[object, ...] = (
        object(),
        _UndescribedComponent("JSON Encoder"),
    )
    for component in invalid_components:
        _assert_raises(
            TypeError,
            lambda component=component: SelectedComponent(
                _role(), cast(_Component, component), descriptor
            ),
            "component must be a RuntimeComponent",
        )


def test_selected_component_requires_component_descriptor_field() -> None:
    """Verify the explicit metadata snapshot has its nominal immutable type."""
    descriptor = _descriptor()
    component = _Component(descriptor)

    # The wrapper never converts mappings or strings into component metadata;
    # descriptor construction and validation remain owned by ComponentDescriptor.
    invalid_descriptors: tuple[object, ...] = ({"name": "JSON Encoder"}, "JSON")
    for invalid_descriptor in invalid_descriptors:
        _assert_raises(
            TypeError,
            lambda invalid_descriptor=invalid_descriptor: SelectedComponent(
                _role(),
                component,
                cast(ComponentDescriptor, invalid_descriptor),
            ),
            "descriptor must be a ComponentDescriptor",
        )


def test_selected_component_rejects_malformed_component_metadata() -> None:
    """Verify structural field presence cannot hide an invalid descriptor value."""
    component = _MalformedComponent("not component metadata")

    # Runtime structural checks establish field presence; this value then checks
    # the field's nominal type before accepting it into the execution snapshot.
    _assert_raises(
        TypeError,
        lambda: SelectedComponent(_role(), cast(_Component, component), _descriptor()),
        "component descriptor must be a ComponentDescriptor",
    )


def test_selected_component_rejects_mismatched_descriptor_snapshot() -> None:
    """Verify explicit metadata cannot describe a different component."""
    component = _Component(_descriptor("JSON Encoder"))

    # Rejecting mismatch prevents type and capability validation from observing
    # metadata that differs from the component selected for actual execution.
    _assert_raises(
        ValueError,
        lambda: SelectedComponent(_role(), component, _descriptor("CBOR Encoder")),
        "descriptor must match the component descriptor",
    )
