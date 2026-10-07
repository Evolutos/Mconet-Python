"""Value and boundary tests for transport component selection criteria."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import TransportSelection


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match a field-specific fragment so unrelated setup failures cannot make
        # a negative transport-selection test appear successful.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_transport_selection_preserves_kind_and_required_capabilities() -> None:
    """Verify complete transport criteria retain exact open identifiers."""
    transport_kind = OpenIdentifier("vendor.rpc")
    capabilities = frozenset(
        (
            OpenIdentifier("transport.unary"),
            OpenIdentifier("transport.tls"),
        )
    )

    selection = TransportSelection(transport_kind, capabilities)

    # Both immutable inputs retain identity; the selection does not normalize an
    # unknown kind or rebuild the already immutable capability requirement set.
    assert selection.transport_kind is transport_kind
    assert selection.required_capabilities is capabilities
    assert {str(capability) for capability in selection.required_capabilities} == {
        "transport.unary",
        "transport.tls",
    }


def test_transport_selection_supports_independently_optional_constraints() -> None:
    """Verify kind and capability constraints can be omitted independently."""
    transport_kind = OpenIdentifier("transport.http")
    requirement = OpenIdentifier("transport.streaming")
    unconstrained = TransportSelection()
    kind_only = TransportSelection(transport_kind=transport_kind)
    capability_only = TransportSelection(
        required_capabilities=frozenset((requirement,))
    )

    # Absence remains None or an empty immutable set; no default protocol kind or
    # capability is inferred from the other selection dimension.
    assert unconstrained.transport_kind is None
    assert unconstrained.required_capabilities == frozenset()
    assert kind_only.transport_kind is transport_kind
    assert kind_only.required_capabilities == frozenset()
    assert capability_only.transport_kind is None
    assert capability_only.required_capabilities == frozenset((requirement,))


def test_transport_selection_uses_set_membership_semantics() -> None:
    """Verify duplicate requirements collapse and declaration order is irrelevant."""
    unary = OpenIdentifier("transport.unary")
    tls = OpenIdentifier("transport.tls")
    with_duplicate = TransportSelection(
        required_capabilities=frozenset((unary, tls, OpenIdentifier("transport.unary")))
    )
    reversed_order = TransportSelection(required_capabilities=frozenset((tls, unary)))

    # Language-neutral Set semantics compare membership only, so repeated equal
    # identifiers and source ordering cannot alter resolution requirements.
    assert len(with_duplicate.required_capabilities) == 2
    assert with_duplicate == reversed_order
    assert hash(with_duplicate) == hash(reversed_order)


def test_transport_selection_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen fields cover both criteria."""
    first = TransportSelection(
        OpenIdentifier("transport.http"),
        frozenset((OpenIdentifier("transport.unary"),)),
    )
    same = TransportSelection(
        OpenIdentifier("transport.http"),
        frozenset((OpenIdentifier("transport.unary"),)),
    )
    different = TransportSelection(OpenIdentifier("transport.grpc"))

    # Kind and requirements jointly define one hashable resolution snapshot; no
    # consumer can replace either field once component resolution begins.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert not hasattr(first.required_capabilities, "add")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("transport_kind", OpenIdentifier("changed")),
        "cannot assign to field",
    )


def test_transport_selection_exposes_only_resolution_constraints() -> None:
    """Verify component identity and descriptor metadata stay outside selection."""
    selection = TransportSelection()

    # The exact field surface prevents a protocol plan from naming a component,
    # embedding a Transport instance, or copying all declared capabilities.
    assert tuple(field.name for field in fields(TransportSelection)) == (
        "transport_kind",
        "required_capabilities",
    )
    assert not hasattr(selection, "component_id")
    assert not hasattr(selection, "transport")
    assert not hasattr(selection, "declared_capabilities")


def test_transport_selection_requires_optional_open_kind() -> None:
    """Verify a raw string and unrelated objects cannot replace transport kind."""
    # All kinds use the shared open identifier representation so future protocol
    # families remain exact without allowing primitive substitutes.
    invalid_values: tuple[object, ...] = ("transport.http", 1, object())
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: TransportSelection(
                transport_kind=cast(OpenIdentifier, value)
            ),
            "transport_kind must be an OpenIdentifier or None",
        )


def test_transport_selection_requires_immutable_capability_set() -> None:
    """Verify mutable and ordered collections cannot become requirements."""
    # Callers must choose Set semantics explicitly; construction never snapshots a
    # mutable set or silently discards tuple/list ordering and duplicates.
    invalid_values: tuple[object, ...] = (
        {OpenIdentifier("transport.unary")},
        (OpenIdentifier("transport.unary"),),
        [OpenIdentifier("transport.unary")],
    )
    for value in invalid_values:
        _assert_raises(
            TypeError,
            lambda value=value: TransportSelection(
                required_capabilities=cast(frozenset[OpenIdentifier], value)
            ),
            "required_capabilities must be a frozenset",
        )


def test_transport_selection_requires_open_capability_values() -> None:
    """Verify every immutable requirement member uses OpenIdentifier."""
    # A frozenset alone does not establish nominal member types; validate every
    # dynamic element before resolution reads capability membership.
    _assert_raises(
        TypeError,
        lambda: TransportSelection(
            required_capabilities=cast(
                frozenset[OpenIdentifier], frozenset(("transport.unary",))
            )
        ),
        "required_capabilities must contain OpenIdentifier values",
    )
