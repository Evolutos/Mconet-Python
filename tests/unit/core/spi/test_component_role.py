"""Open-value tests for execution-chain component roles."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import ComponentRole

_STANDARD_ROLES = (
    "task.protocol-adapter",
    "codec.request.encoder",
    "codec.response.success-decoder",
    "codec.response.error-decoder",
    "codec.stream.event-decoder",
    "stream.outgoing-encoder",
    "transport.unary",
    "transport.server-stream",
    "transport.client-stream",
    "transport.duplex",
    "stream.framer-factory",
    "stream.event-mapper",
    "stream.accumulator-factory",
    "stream.outgoing-mapper",
    "operation.protocol-adapter",
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
        # Match stable role diagnostics so an unrelated exception cannot make a
        # negative open-value test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_component_role_accepts_every_standard_value() -> None:
    """Verify every standard single-component execution role remains distinct."""
    roles = tuple(ComponentRole(OpenIdentifier(value)) for value in _STANDARD_ROLES)

    # All standards use one open construction path; no Enum branch or implicit
    # alias changes identity across codec, transport, stream, and operation roles.
    assert tuple(str(role) for role in roles) == _STANDARD_ROLES
    assert len(set(roles)) == len(_STANDARD_ROLES)


def test_component_role_preserves_unknown_future_value() -> None:
    """Verify a valid extension role remains exact and distinguishable."""
    identifier = OpenIdentifier("vendor.batch.scheduler")
    role = ComponentRole(identifier)

    # Unknown roles retain identifier identity and text rather than collapsing to
    # a generic role or being mistaken for one of the current standard positions.
    assert role.id is identifier
    assert str(role) == "vendor.batch.scheduler"
    assert role not in {
        ComponentRole(OpenIdentifier(value)) for value in _STANDARD_ROLES
    }


def test_component_role_round_trips_unknown_value_through_json() -> None:
    """Verify ordinary plan serialization preserves extension role text."""
    role = ComponentRole(OpenIdentifier("vendor.batch.scheduler"))

    # Serialize only the owned open identifier and reconstruct without consulting
    # a closed role registry or falling back to an unknown sentinel.
    encoded = json.dumps({"role": str(role)}, sort_keys=True)
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = ComponentRole(OpenIdentifier(decoded["role"]))

    assert restored == role
    assert restored.id is not role.id
    assert str(restored) == "vendor.batch.scheduler"


def test_component_role_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and frozen storage depend only on role ID."""
    first = ComponentRole(OpenIdentifier("transport.unary"))
    same = ComponentRole(OpenIdentifier("transport.unary"))
    different = ComponentRole(OpenIdentifier("transport.duplex"))

    # Role identity forms a stable hashable plan fact and cannot change after
    # component resolution associates it with a selected implementation.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("transport.unary")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", OpenIdentifier("transport.duplex")),
        "cannot assign to field",
    )


def test_component_role_contains_only_execution_position_identity() -> None:
    """Verify component and configuration details remain outside role values."""
    role = ComponentRole(OpenIdentifier("codec.request.encoder"))

    # The one-field surface keeps a role distinct from component IDs, selected
    # instances, descriptors, injection fields, and capability requirements.
    assert tuple(field.name for field in fields(ComponentRole)) == ("id",)
    assert not hasattr(role, "component_id")
    assert not hasattr(role, "component")
    assert not hasattr(role, "descriptor")
    assert not hasattr(role, "required_capabilities")


def test_component_role_rejects_invalid_open_identifiers() -> None:
    """Verify standard and extension roles use portable identifier syntax."""
    invalid_values = (
        "",
        "Transport.Unary",
        "transport unary",
        "transport/unary",
        ".transport.unary",
    )

    # Every malformed value reaches the shared open identifier validator, keeping
    # role portability aligned with other cross-platform open value contracts.
    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: ComponentRole(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_component_role_requires_open_identifier() -> None:
    """Verify a bare string cannot bypass the nominal role identity boundary."""
    # Static casts cannot alter runtime storage; callers must construct the common
    # OpenIdentifier value before a role can enter a plan or selection snapshot.
    _assert_raises(
        TypeError,
        lambda: ComponentRole(cast(OpenIdentifier, "transport.unary")),
        "id must be an OpenIdentifier",
    )
