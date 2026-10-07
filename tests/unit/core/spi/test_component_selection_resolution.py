"""Collection tests for immutable component selection results."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentRole,
    ComponentSelectionResolution,
    SelectedComponent,
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
        # Match resolution-owned wording so failures in fixture construction or
        # component metadata cannot accidentally satisfy a collection test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Application component exposing the structural runtime metadata boundary."""

    descriptor: ComponentDescriptor
    """Immutable metadata used to construct a selected component snapshot."""


def _selected(
    role_id: str,
    *,
    component: _Component | None = None,
) -> SelectedComponent:
    """Build one valid selected component with distinguishable role metadata."""
    # Reuse a supplied component only when a test needs to prove one instance can
    # fulfill multiple roles; otherwise each fixture represents a separate choice.
    descriptor = ComponentDescriptor(role_id, "1.0", "application")
    selected_component = component or _Component(descriptor)
    return SelectedComponent(
        ComponentRole(OpenIdentifier(role_id)),
        selected_component,
        selected_component.descriptor,
    )


def test_component_selection_resolution_preserves_order_and_identity() -> None:
    """Verify selected component snapshots remain in exact resolver order."""
    encoder = _selected("codec.request.encoder")
    transport = _selected("transport.unary")
    components = (encoder, transport)

    resolution = ComponentSelectionResolution(components)

    # Retaining the original tuple avoids a redundant copy while identity and
    # order preserve the exact immutable result produced by component resolution.
    assert resolution.components is components
    assert resolution.components == (encoder, transport)


def test_component_selection_resolution_defaults_to_empty_tuple() -> None:
    """Verify no selected components use one explicit immutable empty state."""
    resolution = ComponentSelectionResolution()

    # An empty tuple avoids nullable and mutable empty-state variants while still
    # allowing a resolver to represent a plan that selects no unique roles.
    assert resolution.components == ()
    assert isinstance(resolution.components, tuple)


def test_component_selection_resolution_has_immutable_value_semantics() -> None:
    """Verify collection membership participates in frozen value identity."""
    encoder = _selected("codec.request.encoder")
    transport = _selected("transport.unary")
    first = ComponentSelectionResolution((encoder, transport))
    same = ComponentSelectionResolution((encoder, transport))
    reversed_order = ComponentSelectionResolution((transport, encoder))

    # Resolver order remains part of the result value, and neither the containing
    # tuple nor frozen field can be changed after an interaction captures it.
    assert first == same
    assert hash(first) == hash(same)
    assert first != reversed_order
    assert not hasattr(first.components, "append")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("components", ()),
        "cannot assign to field",
    )


def test_component_selection_resolution_exposes_only_selected_components() -> None:
    """Verify input-dispatched candidates are not invented as role selections."""
    resolution = ComponentSelectionResolution()

    # The exact architecture surface contains the selected-role tuple only;
    # specialized candidate lists belong to the later execution snapshot.
    assert tuple(field.name for field in fields(ComponentSelectionResolution)) == (
        "components",
    )
    assert not hasattr(resolution, "authorization_handlers")
    assert not hasattr(resolution, "artifact_readers")
    assert not hasattr(resolution, "capability_providers")


def test_component_selection_resolution_requires_tuple_storage() -> None:
    """Verify mutable and unordered collections cannot become the snapshot."""
    selected = _selected("transport.unary")
    invalid_collections = (
        cast(object, [selected]),
        cast(object, {selected}),
        cast(object, frozenset[object]()),
    )

    # Construction never performs a silent defensive conversion because that
    # could hide caller mutation expectations or discard deterministic ordering.
    for components in invalid_collections:
        _assert_raises(
            TypeError,
            lambda components=components: ComponentSelectionResolution(
                cast(tuple[SelectedComponent, ...], components)
            ),
            "components must be a tuple",
        )


def test_component_selection_resolution_requires_selected_component_members() -> None:
    """Verify every tuple member is a complete selected component snapshot."""
    invalid_members: tuple[object, ...] = (
        _selected("transport.unary").component,
        ComponentRole(OpenIdentifier("transport.unary")),
        "transport.unary",
    )

    # Neither a raw component, standalone role, nor role string carries the full
    # role/component/descriptor combination needed by downstream validation.
    for member in invalid_members:
        _assert_raises(
            TypeError,
            lambda member=member: ComponentSelectionResolution(
                cast(tuple[SelectedComponent, ...], (member,))
            ),
            "components must contain SelectedComponent values",
        )


def test_component_selection_resolution_rejects_duplicate_roles() -> None:
    """Verify one execution-chain role cannot resolve to two components."""
    first = _selected("transport.unary")
    second = _selected("transport.unary")

    # Equal open role values represent the same single-value slot even when the
    # concrete component snapshots were created independently.
    _assert_raises(
        ValueError,
        lambda: ComponentSelectionResolution((first, second)),
        "components must use unique roles",
    )


def test_resolution_allows_shared_component_for_distinct_roles() -> None:
    """Verify uniqueness applies to roles rather than component object identity."""
    shared_descriptor = ComponentDescriptor("Shared Codec", "1.0", "application")
    shared_component = _Component(shared_descriptor)
    encoder = _selected("codec.request.encoder", component=shared_component)
    decoder = _selected("codec.response.success-decoder", component=shared_component)

    resolution = ComponentSelectionResolution((encoder, decoder))

    # A stateless implementation may implement multiple SPI roles; preserving the
    # same instance is valid because each execution position remains unique.
    assert resolution.components[0].component is shared_component
    assert resolution.components[1].component is shared_component
