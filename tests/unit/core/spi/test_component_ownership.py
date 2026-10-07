"""Open-value tests for immutable component lifecycle ownership identities."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import ComponentOwnership

_STANDARD_OWNERS = ("builtin", "application")


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require one action to fail with the intended type and stable text."""
    try:
        action()
    except exception_type as error:
        # Match a stable fragment so an unrelated constructor failure cannot make
        # a negative ownership test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_component_ownership_accepts_standard_values() -> None:
    """Represent SDK-owned and application-owned lifecycles distinctly."""
    ownerships = tuple(
        ComponentOwnership(OpenIdentifier(value)) for value in _STANDARD_OWNERS
    )

    # Both current values use the same open constructor path. The value object
    # records owner identity only and performs no component close operation.
    assert tuple(str(ownership) for ownership in ownerships) == _STANDARD_OWNERS
    assert ownerships[0] != ownerships[1]
    assert len(set(ownerships)) == 2


def test_component_ownership_preserves_unknown_future_value() -> None:
    """Retain an extension ownership identity without fallback or normalization."""
    identifier = OpenIdentifier("vendor.shared-owner")

    ownership = ComponentOwnership(identifier)

    # Unknown values preserve both nominal identifier identity and exact text;
    # they do not collapse to builtin, application, or an unknown sentinel.
    assert ownership.id is identifier
    assert str(ownership) == "vendor.shared-owner"
    assert ownership not in {
        ComponentOwnership(OpenIdentifier(value)) for value in _STANDARD_OWNERS
    }


def test_component_ownership_round_trips_unknown_value_through_json() -> None:
    """Preserve an extension owner through ordinary value serialization."""
    ownership = ComponentOwnership(OpenIdentifier("vendor.transferred"))

    # Serialize only the public identifier text and reconstruct through the same
    # validated path used by standard values, without consulting a registry.
    encoded = json.dumps({"ownership": str(ownership)}, sort_keys=True)
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = ComponentOwnership(OpenIdentifier(decoded["ownership"]))

    assert restored == ownership
    assert restored.id is not ownership.id
    assert str(restored) == "vendor.transferred"


def test_component_ownership_has_immutable_value_semantics() -> None:
    """Base equality, hashing, and frozen storage only on ownership identity."""
    first = ComponentOwnership(OpenIdentifier("builtin"))
    same = ComponentOwnership(OpenIdentifier("builtin"))
    different = ComponentOwnership(OpenIdentifier("application"))

    # Hashable frozen values can accompany component snapshots without mutable
    # release state, owner instances, or reference-counting behavior.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("builtin")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", OpenIdentifier("application")),
        "cannot assign to field",
    )
    assert not hasattr(first, "__dict__")


def test_component_ownership_contains_only_open_owner_identity() -> None:
    """Exclude component metadata, source inference, and release behavior."""
    ownership = ComponentOwnership(OpenIdentifier("application"))

    # The one-field surface prevents this value from becoming an owned-component
    # wrapper, a Descriptor source alias, or a lifecycle manager prematurely.
    assert tuple(field.name for field in fields(ComponentOwnership)) == ("id",)
    for absent_member in (
        "component",
        "descriptor",
        "source",
        "close",
        "release",
        "is_closed",
        "reference_count",
        "transferred",
    ):
        assert not hasattr(ownership, absent_member)


def test_component_ownership_does_not_infer_from_descriptor_source_text() -> None:
    """Keep provenance strings distinct from explicit lifecycle ownership."""
    plugin_owned_by_application = ComponentOwnership(OpenIdentifier("application"))
    builtin_named_extension = ComponentOwnership(OpenIdentifier("plugin"))

    # The open value can preserve future text, but construction never receives a
    # component or Descriptor and therefore cannot infer lifecycle authority.
    assert str(plugin_owned_by_application) == "application"
    assert str(builtin_named_extension) == "plugin"
    assert plugin_owned_by_application != builtin_named_extension


def test_component_ownership_rejects_invalid_open_identifiers() -> None:
    """Apply the common portable identifier grammar to every owner value."""
    invalid_values = (
        "",
        "BuiltIn",
        "application owned",
        "vendor/owner",
        ".application",
    )

    for value in invalid_values:
        # Standard-looking and future values share identical syntax validation;
        # no closed enum branch supplies an alternate error or fallback.
        _assert_raises(
            ValueError,
            lambda value=value: ComponentOwnership(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_component_ownership_requires_open_identifier() -> None:
    """Reject a bare string that bypasses the nominal identifier boundary."""
    # A static cast cannot change runtime storage. All callers must construct the
    # common immutable OpenIdentifier before recording lifecycle ownership.
    _assert_raises(
        TypeError,
        lambda: ComponentOwnership(cast(OpenIdentifier, "builtin")),
        "id must be an OpenIdentifier",
    )
