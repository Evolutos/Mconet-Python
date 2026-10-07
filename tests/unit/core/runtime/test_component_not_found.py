"""Stable missing-error tests for required single-component selection."""

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
        # A narrow exception boundary prevents fixture or matcher failures from
        # accidentally satisfying the normalized missing-error assertion.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Component:
    """Minimal runtime component used to distinguish source candidates."""

    descriptor: ComponentDescriptor
    """Immutable metadata that must never enter the fixed missing-error text."""


def _component(name: str) -> _Component:
    """Build one component with application-controlled diagnostic metadata."""
    # A private-looking name makes accidental descriptor leakage observable while
    # remaining a non-secret deterministic test fixture.
    return _Component(ComponentDescriptor(name, "1.0.0", "application"))


def _role(value: str = "vendor.private-required-role") -> ComponentRole:
    """Build one open required role whose text must not enter the error."""
    # The open role exercises forward-compatible identifiers without requiring a
    # closed standard-role catalog in the missing branch.
    return ComponentRole(OpenIdentifier(value))


def _layers(
    interaction: tuple[RuntimeComponent, ...] = (),
    client: tuple[RuntimeComponent, ...] = (),
    integration: tuple[RuntimeComponent, ...] = (),
    sdk_default: tuple[RuntimeComponent, ...] = (),
) -> ComponentSourceLayers:
    """Build fixed source layers for required-selection test scenarios."""
    # Named fields preserve exact production priority without introducing a
    # parallel role map or test-only lookup algorithm.
    return interaction, client, integration, sdk_default


def _matches_all(component: RuntimeComponent) -> bool:
    """Accept every component for successful and ambiguous branch isolation."""
    # No metadata or behavior inspection is required when testing cardinality.
    del component
    return True


def test_required_selection_raises_stable_error_when_all_layers_are_empty() -> None:
    """Normalize total required-role absence as component_not_found."""
    role = _role()
    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(role, _layers(), _matches_all),
            "No matching component was found for a required role",
        ),
    )

    # Portable category, phase, code, and fixed text fully describe this Core
    # configuration failure without service-owned or recovery metadata.
    assert error.category.id == OpenIdentifier("invalid_component_configuration")
    assert error.phase.id == OpenIdentifier("component_resolution")
    assert error.code == "component_not_found"
    assert error.message == "No matching component was found for a required role."
    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None


def test_required_selection_raises_when_highest_present_layer_has_no_match() -> None:
    """Reject an incompatible explicit override without lower-layer fallback."""
    explicit = _component("application-private-encoder")
    lower = _component("sdk-default-encoder")
    observed: list[RuntimeComponent] = []

    def matches_lower(component: RuntimeComponent) -> bool:
        """Record evaluations and match only the forbidden lower fallback."""
        # If the algorithm incorrectly descends after an explicit mismatch, this
        # callback would observe and accept the lower SDK candidate.
        observed.append(component)
        return component is lower

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                _role(),
                _layers(interaction=(explicit,), sdk_default=(lower,)),
                matches_lower,
            ),
            "No matching component was found for a required role",
        ),
    )

    # The explicit layer remains final even when it has zero compatible members;
    # lower defaults are not inspected, and the stable missing code is retained.
    assert observed == [explicit]
    assert error.code == "component_not_found"


def test_required_selection_returns_the_exact_unique_snapshot() -> None:
    """Pass one successful selection through without rebuilding its values."""
    component = _component("selected-component")
    role = _role("codec.request.encoder")

    selected = select_required_component(
        role,
        _layers(integration=(component,)),
        _matches_all,
    )

    # A successful required branch preserves the same role, component, and
    # descriptor identities established by the common selector.
    assert isinstance(selected, SelectedComponent)
    assert selected.role is role
    assert selected.component is component
    assert selected.descriptor is component.descriptor


def test_required_selection_does_not_mislabel_ambiguity_as_missing() -> None:
    """Keep same-layer multiplicity distinct from component_not_found."""
    first = _component("first")
    second = _component("second")

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                _role(),
                _layers(client=(first, second)),
                _matches_all,
            ),
            "Multiple matching components were found",
        ),
    )

    # The separate stable code proves the missing branch remains exclusive to
    # zero matches after the required selector becomes total.
    assert error.code == "ambiguous_component_selection"
    assert error.code != "component_not_found"


def test_missing_error_omits_open_role_and_component_metadata() -> None:
    """Keep application-controlled identifiers out of normalized error text."""
    private_role = "vendor.secret-shaped-role"
    private_component = "application-secret-shaped-component"
    role = _role(private_role)
    component = _component(private_component)

    def matches_none(candidate: RuntimeComponent) -> bool:
        """Reject the sole explicit component without exposing its metadata."""
        # Identity comparison is deterministic and never reads the diagnostic
        # descriptor fields whose absence from the error is under test.
        return candidate is not component

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_required_component(
                role,
                _layers(interaction=(component,)),
                matches_none,
            ),
            "No matching component was found for a required role",
        ),
    )

    # Neither an open role nor descriptor metadata becomes ordinary exception
    # text, service metadata, a recovery hint, or an attached underlying cause.
    assert private_role not in str(error)
    assert private_component not in str(error)
    assert error.service_error_code is None
    assert error.recovery is None
    assert error.cause is None


def test_missing_branch_preserves_selector_input_errors() -> None:
    """Do not normalize malformed internal inputs as a missing component."""
    role = _role()

    # The common selector owns shape and matcher validation. Propagating its
    # TypeError keeps programmer/configuration bugs distinct from valid absence.
    _assert_raises(
        TypeError,
        lambda: select_required_component(
            role,
            cast(ComponentSourceLayers, [(), (), (), ()]),
            _matches_all,
        ),
        "layers must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: select_required_component(
            role,
            _layers(),
            cast(Callable[[RuntimeComponent], bool], object()),
        ),
        "matches must be callable",
    )
