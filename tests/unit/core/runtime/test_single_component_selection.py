"""Priority and uniqueness tests for internal single-component selection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._single_component_selection import select_single_component
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentRole,
    RuntimeComponent,
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
        # Match selector-owned wording so malformed fixture construction cannot
        # accidentally satisfy an input-boundary assertion.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Minimal structural runtime component for source selection tests."""

    descriptor: ComponentDescriptor
    """Immutable metadata captured when this exact instance is selected."""


def _component(name: str) -> _Component:
    """Build one distinguishable component without executable role behavior."""
    # Names are diagnostic markers only; assertions use concrete identity so the
    # selector cannot pass by performing label-based lookup or reconstruction.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _role(value: str = "codec.request.encoder") -> ComponentRole:
    """Build one valid open component role for selection snapshots."""
    # An explicit open identifier proves selection uses a role value rather than
    # treating a component name or configuration field as a registry key.
    return ComponentRole(OpenIdentifier(value))


def _layers(
    interaction: tuple[RuntimeComponent, ...] = (),
    client: tuple[RuntimeComponent, ...] = (),
    integration: tuple[RuntimeComponent, ...] = (),
    sdk_default: tuple[RuntimeComponent, ...] = (),
) -> ComponentSourceLayers:
    """Build the exact fixed source shape expected from source merging."""
    # Named parameters keep fixture intent readable while the returned tuple
    # preserves the production priority positions without adding test logic.
    return interaction, client, integration, sdk_default


def _matches_all(component: RuntimeComponent) -> bool:
    """Accept every structurally valid component for pure precedence tests."""
    # Touch no behavior or metadata: these tests isolate layer and cardinality
    # semantics while the component argument proves the callback shape is exact.
    del component
    return True


def test_selection_uses_the_highest_non_empty_source_layer() -> None:
    """Choose Interaction before Client, integration, and SDK defaults."""
    interaction = _component("interaction")
    client = _component("client")
    integration = _component("integration")
    sdk_default = _component("default")
    role = _role()

    selected = select_single_component(
        role,
        _layers(
            (interaction,),
            (client,),
            (integration,),
            (sdk_default,),
        ),
        _matches_all,
    )

    # A present higher layer is final for source precedence. Lower components are
    # neither consulted nor used as compatibility fallbacks.
    assert isinstance(selected, SelectedComponent)
    assert selected.role is role
    assert selected.component is interaction
    assert selected.descriptor is interaction.descriptor


def test_selection_falls_through_only_empty_higher_layers() -> None:
    """Select each lower layer when every higher layer is explicitly empty."""
    components = (
        _component("interaction"),
        _component("client"),
        _component("integration"),
        _component("default"),
    )

    # Each case leaves all higher positions empty. Identity checks prove that
    # tuple compression, source inference, and default reconstruction do not occur.
    for index, expected in enumerate(components):
        sources: list[tuple[RuntimeComponent, ...]] = [(), (), (), ()]
        sources[index] = (expected,)
        selected = select_single_component(
            _role(f"fixture.role-{index}"),
            cast(ComponentSourceLayers, tuple(sources)),
            _matches_all,
        )
        assert selected is not None
        assert selected.component is expected


def test_selection_returns_none_when_every_source_layer_is_empty() -> None:
    """Leave missing-role interpretation to the following error branch."""
    selected = select_single_component(_role(), _layers(), _matches_all)

    # None is an intermediate absence signal only; this function does not know
    # whether the planned role is required and cannot create component_not_found.
    assert selected is None


def test_selection_returns_none_for_highest_layer_ambiguity_without_fallback() -> None:
    """Avoid selecting by tuple order or falling back from multiple candidates."""
    first = _component("first")
    second = _component("second")
    lower = _component("lower")

    selected = select_single_component(
        _role(),
        _layers(client=(first, second), integration=(lower,)),
        _matches_all,
    )

    # The two Client candidates remain unresolved. Returning None preserves the
    # condition for the later stable ambiguity error instead of choosing first,
    # sorting by name, or silently accepting the integration candidate.
    assert selected is None


def test_selection_filters_only_the_highest_layer_before_uniqueness() -> None:
    """Select the sole matching candidate from a multi-candidate source layer."""
    first = _component("first")
    second = _component("second")
    lower = _component("lower")

    def matches_second(component: RuntimeComponent) -> bool:
        """Match only the intended Client-layer fixture by concrete identity."""
        # Identity supplies a deterministic test condition without turning the
        # diagnostic component name into a selection key.
        return component is second

    selected = select_single_component(
        _role(),
        _layers(client=(first, second), integration=(lower,)),
        matches_second,
    )

    # Filtering precedes cardinality within the chosen layer, so two raw
    # candidates with exactly one match produce one stable selection.
    assert selected is not None
    assert selected.component is second


def test_selection_does_not_fall_back_when_the_highest_layer_has_no_match() -> None:
    """Treat an incompatible explicit layer as final rather than using defaults."""
    explicit = _component("explicit")
    lower = _component("lower")
    observed: list[RuntimeComponent] = []

    def matches_lower(component: RuntimeComponent) -> bool:
        """Record evaluated candidates and match only the lower-layer fixture."""
        # Observation proves the fixed algorithm never evaluates a lower source
        # after a higher source is present, even when the higher candidate fails.
        observed.append(component)
        return component is lower

    selected = select_single_component(
        _role(),
        _layers(interaction=(explicit,), sdk_default=(lower,)),
        matches_lower,
    )

    # The later missing/incompatibility branch receives None; lower defaults are
    # not a compatibility fallback for an explicit application override.
    assert selected is None
    assert observed == [explicit]


def test_selection_preserves_exact_component_and_descriptor_identity() -> None:
    """Create one selected snapshot without copying component metadata."""
    descriptor = ComponentDescriptor("shared-codec", "2.0.0", "plugin")
    component = _Component(descriptor)
    role = _role("codec.response.success-decoder")

    selected = select_single_component(
        role,
        _layers(integration=(component,)),
        _matches_all,
    )

    # SelectedComponent receives the original role, instance, and immutable
    # descriptor, so later validation observes the exact selection-time facts.
    assert selected is not None
    assert selected.role is role
    assert selected.component is component
    assert selected.descriptor is descriptor


def test_selection_validates_the_fixed_layer_boundary() -> None:
    """Reject alternate priorities, mutable layers, and unrelated members."""
    role = _role()
    component = _component("component")

    # Strict shape validation prevents arbitrary lists, generic role maps, and a
    # fifth source from creating an undocumented component precedence scheme.
    _assert_raises(
        TypeError,
        lambda: select_single_component(
            cast(ComponentRole, "codec.request.encoder"),
            _layers(),
            _matches_all,
        ),
        "role must be a ComponentRole",
    )
    _assert_raises(
        TypeError,
        lambda: select_single_component(
            role,
            cast(ComponentSourceLayers, [(), (), (), ()]),
            _matches_all,
        ),
        "layers must be a tuple",
    )
    _assert_raises(
        ValueError,
        lambda: select_single_component(
            role,
            cast(ComponentSourceLayers, ((), (), ())),
            _matches_all,
        ),
        "layers must contain exactly four source layers",
    )
    _assert_raises(
        TypeError,
        lambda: select_single_component(
            role,
            cast(ComponentSourceLayers, ((component,), [], (), ())),
            _matches_all,
        ),
        "each component source layer must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: select_single_component(
            role,
            cast(
                ComponentSourceLayers, ((cast(RuntimeComponent, object()),), (), (), ())
            ),
            _matches_all,
        ),
        "component source layers must contain RuntimeComponent values",
    )


def test_selection_requires_a_callable_with_exact_boolean_results() -> None:
    """Reject hidden ranking values and malformed internal matching inputs."""
    component = _component("component")

    def returns_score(candidate: RuntimeComponent) -> bool:
        """Return a dynamically invalid integer score for boundary testing."""
        # Consume the candidate without behavior calls, then use a cast solely to
        # cross static typing and verify the runtime exact-boolean invariant.
        del candidate
        return cast(bool, 1)

    # An internal matcher is required, and its output cannot smuggle ranking or
    # truthiness semantics into the deterministic uniqueness algorithm.
    _assert_raises(
        TypeError,
        lambda: select_single_component(
            _role(),
            _layers(interaction=(component,)),
            cast(Callable[[RuntimeComponent], bool], object()),
        ),
        "matches must be callable",
    )
    _assert_raises(
        TypeError,
        lambda: select_single_component(
            _role(),
            _layers(interaction=(component,)),
            returns_score,
        ),
        "matches must return a boolean",
    )


def test_selection_exposes_no_registry_or_component_id_inputs() -> None:
    """Keep role selection independent from names, IDs, and service locators."""
    signature_names = tuple(select_single_component.__annotations__)

    # Inputs are the semantic role, merged layers, and one Core-owned pure match
    # condition; no registry, component ID, binding key, or generic map can
    # influence the fixed precedence and uniqueness algorithm.
    assert signature_names == ("role", "layers", "matches", "return")
