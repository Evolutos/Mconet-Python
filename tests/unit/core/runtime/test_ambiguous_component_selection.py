"""Stable ambiguity-error tests for required single-component selection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import ModelInteractionError, OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._single_component_selection import (
    select_required_component,
)
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
) -> BaseException:
    """Return an expected exception after matching its message fragment."""
    try:
        action()
    except exception_type as error:
        # Restrict the boundary so fixture and matcher failures cannot satisfy an
        # ambiguity assertion merely because they also raise an exception.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Minimal structural component with distinguishable diagnostic metadata."""

    descriptor: ComponentDescriptor
    """Immutable metadata excluded from normalized ambiguity error text."""


def _component(name: str) -> _Component:
    """Build one concrete candidate whose identity is independently observable."""
    # A diagnostic name helps prove that selection never sorts, identifies, or
    # reports candidates through application-controlled descriptor text.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _role(value: str = "vendor.private-required-role") -> ComponentRole:
    """Build an open component role for required-selection scenarios."""
    # Open role text exercises forward compatibility and the error redaction
    # boundary without requiring a closed role enumeration.
    return ComponentRole(OpenIdentifier(value))


def _layers(
    interaction: tuple[RuntimeComponent, ...] = (),
    client: tuple[RuntimeComponent, ...] = (),
    integration: tuple[RuntimeComponent, ...] = (),
    sdk_default: tuple[RuntimeComponent, ...] = (),
) -> ComponentSourceLayers:
    """Build one exact fixed-priority candidate-layer tuple."""
    # Named arguments keep test intent explicit while production tuple positions
    # remain the only source-priority representation.
    return interaction, client, integration, sdk_default


def _matches_all(component: RuntimeComponent) -> bool:
    """Accept every valid component to isolate same-layer cardinality."""
    # No component behavior or descriptor data participates in this condition.
    del component
    return True


def test_required_selection_raises_stable_same_layer_ambiguity_error() -> None:
    """Normalize multiple highest-layer matches before any execution begins."""
    first = _component("first-private-component")
    second = _component("second-private-component")
    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                _role(),
                _layers(client=(first, second)),
                _matches_all,
            ),
            "Multiple matching components were found at the same source priority",
        ),
    )

    # The normalized Core configuration error uses fixed portable fields and no
    # service response, retry, request, or underlying exception metadata.
    assert error.category.id == OpenIdentifier("invalid_component_configuration")
    assert error.phase.id == OpenIdentifier("component_resolution")
    assert error.code == "ambiguous_component_selection"
    assert error.message == (
        "Multiple matching components were found at the same source priority."
    )
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_ambiguity_uses_matches_not_raw_candidate_count() -> None:
    """Select one compatible candidate from multiple raw same-layer entries."""
    first = _component("first")
    second = _component("second")

    def matches_second(component: RuntimeComponent) -> bool:
        """Match only the intended second candidate by concrete identity."""
        # Identity avoids treating descriptor names as resolver keys.
        return component is second

    selected = select_required_component(
        _role("codec.response.success-decoder"),
        _layers(integration=(first, second)),
        matches_second,
    )

    # Raw multiplicity is valid when role-specific filtering yields one match;
    # the unique selected snapshot retains the exact compatible instance.
    assert isinstance(selected, SelectedComponent)
    assert selected.component is second


def test_ambiguity_does_not_evaluate_or_fall_back_to_lower_layers() -> None:
    """Stop after multiple matches in the highest non-empty source layer."""
    first = _component("z-client")
    second = _component("a-client")
    lower = _component("integration")
    observed: list[RuntimeComponent] = []

    def record_match(component: RuntimeComponent) -> bool:
        """Record every evaluated candidate while accepting all of them."""
        # Observation proves lower layers remain untouched after Client priority
        # is fixed, even though their candidate would also satisfy the matcher.
        observed.append(component)
        return True

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                _role(),
                _layers(client=(first, second), integration=(lower,)),
                record_match,
            ),
            "Multiple matching components were found",
        ),
    )

    # Declaration order is observed but never used to choose first, last, or a
    # lexically sorted component; the lower integration layer is not evaluated.
    assert observed == [first, second]
    assert error.code == "ambiguous_component_selection"


def test_duplicate_candidate_entries_remain_ambiguous() -> None:
    """Avoid identity deduplication that could conceal invalid source assembly."""
    repeated = _component("repeated")

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                _role(),
                _layers(integration=(repeated, repeated)),
                _matches_all,
            ),
            "Multiple matching components were found",
        ),
    )

    # Two configured candidate entries are ambiguous even when they reference
    # the same object; silently deduplicating would hide the invalid combination.
    assert error.code == "ambiguous_component_selection"


def test_unique_higher_layer_ignores_ambiguous_lower_layer() -> None:
    """Return the unique highest-priority match without inspecting lower ties."""
    interaction = _component("interaction")
    lower_first = _component("lower-first")
    lower_second = _component("lower-second")
    observed: list[RuntimeComponent] = []

    def record_match(component: RuntimeComponent) -> bool:
        """Record evaluated candidates while accepting each observed value."""
        # A correct priority stop records only the unique Interaction candidate.
        observed.append(component)
        return True

    selected = select_required_component(
        _role(),
        _layers(
            interaction=(interaction,),
            integration=(lower_first, lower_second),
        ),
        record_match,
    )

    # Lower ambiguity is irrelevant after a higher unique source wins; checking
    # it would violate field override semantics and create a false failure.
    assert selected.component is interaction
    assert observed == [interaction]


def test_ambiguity_error_omits_role_candidate_names_and_count() -> None:
    """Keep application-controlled selection facts out of exception text."""
    private_role = "vendor.private-secret-shaped-role"
    first_name = "application-private-secret-shaped-first"
    second_name = "plugin-private-secret-shaped-second"
    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                _role(private_role),
                _layers(
                    integration=(
                        _component(first_name),
                        _component(second_name),
                    )
                ),
                _matches_all,
            ),
            "Multiple matching components were found",
        ),
    )

    # Fixed text avoids exposing open identifiers, descriptors, candidate count,
    # or list position through ordinary logs and exception rendering.
    assert private_role not in str(error)
    assert first_name not in str(error)
    assert second_name not in str(error)
    assert "2" not in str(error)


def test_missing_and_invalid_inputs_keep_their_distinct_failures() -> None:
    """Do not replace absence or programmer errors with ambiguity."""
    role = _role()

    missing = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(role, _layers(), _matches_all),
            "No matching component was found",
        ),
    )
    _assert_raises(
        TypeError,
        lambda: select_required_component(
            role,
            cast(ComponentSourceLayers, [(), (), (), ()]),
            _matches_all,
        ),
        "layers must be a tuple",
    )

    # Zero matches retain the missing code, while malformed source storage stays
    # a TypeError owned by the internal selection boundary.
    assert missing.code == "component_not_found"
