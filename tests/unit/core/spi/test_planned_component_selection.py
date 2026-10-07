"""Value and boundary tests for planned component role requirements."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import ComponentRole, PlannedComponentSelection


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match stable owned-field wording so an unrelated fixture error cannot
        # make a negative planned-selection test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _role(value: str = "stream.event-mapper") -> ComponentRole:
    """Build one validated open component role for selection fixtures."""
    # Construct through the public open path so fixture roles observe the same
    # portability rules as execution plans created by protocol adapters.
    return ComponentRole(OpenIdentifier(value))


def test_planned_component_selection_preserves_complete_requirements() -> None:
    """Verify role, presence policy, and capability set remain exact."""
    role = _role()
    capabilities = frozenset(
        (
            OpenIdentifier("stream.structured-events"),
            OpenIdentifier("stream.incremental-output"),
        )
    )

    selection = PlannedComponentSelection(role, True, capabilities)

    # Both nested immutable inputs retain identity, and required remains an exact
    # boolean instead of being inferred from role family or capability count.
    assert selection.role is role
    assert selection.required is True
    assert selection.required_capabilities is capabilities


def test_planned_component_selection_supports_optional_constrained_role() -> None:
    """Verify an optional role may still constrain any component that is present."""
    requirement = OpenIdentifier("stream.resume")
    selection = PlannedComponentSelection(
        _role("stream.accumulator-factory"),
        False,
        frozenset((requirement,)),
    )

    # False permits a missing component but does not discard capability matching
    # when a candidate is available for this execution-chain position.
    assert selection.required is False
    assert selection.required_capabilities == frozenset((requirement,))


def test_planned_component_selection_defaults_to_no_capability_requirements() -> None:
    """Verify an explicit presence policy does not invent capabilities."""
    required = PlannedComponentSelection(_role(), True)
    optional = PlannedComponentSelection(_role(), False)

    # Both presence policies share the same safe immutable empty default; neither
    # role name nor required flag implies a hidden feature requirement.
    assert required.required_capabilities == frozenset()
    assert optional.required_capabilities == frozenset()
    assert required.required_capabilities is optional.required_capabilities


def test_planned_component_selection_uses_set_membership_semantics() -> None:
    """Verify capability duplicates and declaration order do not affect the value."""
    delta = OpenIdentifier("stream.delta")
    usage = OpenIdentifier("stream.usage")
    with_duplicate = PlannedComponentSelection(
        _role(),
        True,
        frozenset((delta, usage, OpenIdentifier("stream.delta"))),
    )
    reversed_order = PlannedComponentSelection(
        _role(),
        True,
        frozenset((usage, delta)),
    )

    # Set membership alone defines requirements, so equal duplicate identifiers
    # collapse and input ordering cannot alter component matching.
    assert len(with_duplicate.required_capabilities) == 2
    assert with_duplicate == reversed_order
    assert hash(with_duplicate) == hash(reversed_order)


def test_planned_component_selection_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields include all plan facts."""
    first = PlannedComponentSelection(_role(), True)
    same = PlannedComponentSelection(_role(), True)
    optional = PlannedComponentSelection(_role(), False)

    # The presence policy participates independently in value identity, and no
    # field or capability member can change during component resolution.
    assert first == same
    assert hash(first) == hash(same)
    assert first != optional
    assert not hasattr(first.required_capabilities, "add")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("required", False),
        "cannot assign to field",
    )


def test_planned_component_selection_exposes_only_plan_requirements() -> None:
    """Verify criteria unions, selected instances, and descriptors stay outside."""
    selection = PlannedComponentSelection(_role(), True)

    # The exact three-field surface follows the plan structure and does not embed
    # codec/transport selections or facts that exist only after resolution.
    assert tuple(field.name for field in fields(PlannedComponentSelection)) == (
        "role",
        "required",
        "required_capabilities",
    )
    assert not hasattr(selection, "encoder_selection")
    assert not hasattr(selection, "decoder_selection")
    assert not hasattr(selection, "transport_selection")
    assert not hasattr(selection, "component")
    assert not hasattr(selection, "descriptor")


def test_planned_component_selection_requires_component_role() -> None:
    """Verify strings and bare identifiers cannot replace the open role value."""
    # Role validation must happen before plan composition; this container never
    # constructs a role implicitly from lower-level identifier representations.
    invalid_values: tuple[object, ...] = (
        "stream.event-mapper",
        OpenIdentifier("stream.event-mapper"),
        object(),
    )
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: PlannedComponentSelection(
                cast(ComponentRole, value), True
            ),
            "role must be a ComponentRole",
        )


def test_planned_component_selection_requires_exact_boolean_policy() -> None:
    """Verify truthy and falsey substitutes cannot become presence policy."""
    # Exact bool storage prevents 0/1 and textual flags from acquiring language-
    # specific coercion semantics when plans cross platform boundaries.
    invalid_values: tuple[object, ...] = (0, 1, "true", None, object())
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: PlannedComponentSelection(_role(), cast(bool, value)),
            "required must be a boolean",
        )


def test_planned_component_selection_requires_immutable_capability_set() -> None:
    """Verify mutable and ordered requirement collections are rejected."""
    # Construction does not silently snapshot collections because that could hide
    # later mutation expectations or discard caller-observed ordering.
    invalid_values: tuple[object, ...] = (
        {OpenIdentifier("stream.delta")},
        (OpenIdentifier("stream.delta"),),
        [OpenIdentifier("stream.delta")],
    )
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: PlannedComponentSelection(
                _role(),
                True,
                cast(frozenset[OpenIdentifier], value),
            ),
            "required_capabilities must be a frozenset",
        )


def test_planned_component_selection_requires_open_capability_values() -> None:
    """Verify every immutable requirement member uses OpenIdentifier."""
    # Validate member types after collection shape so a raw string cannot bypass
    # the shared open capability representation merely by entering a frozenset.
    _assert_raises(
        TypeError,
        lambda: PlannedComponentSelection(
            _role(),
            True,
            cast(frozenset[OpenIdentifier], frozenset(("stream.delta",))),
        ),
        "required_capabilities must contain OpenIdentifier values",
    )
