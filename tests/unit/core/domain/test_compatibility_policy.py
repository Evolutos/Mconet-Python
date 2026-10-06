"""Open-value tests for immutable CompatibilityPolicy modes."""

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import CompatibilityPolicy, OpenIdentifier

_STANDARD_MODES = ("strict", "compatible", "permissive")


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the stable domain diagnostic as well as its type so an unrelated
    # exception cannot make a negative policy test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_compatibility_policy_accepts_every_standard_mode() -> None:
    """Verify strict, compatible, and permissive remain distinct open values."""
    policies = tuple(
        CompatibilityPolicy(OpenIdentifier(mode)) for mode in _STANDARD_MODES
    )

    # The value object records strategy identity only; later processing layers
    # decide the behavioral differences between each standard mode.
    assert tuple(str(policy) for policy in policies) == _STANDARD_MODES
    assert len(set(policies)) == len(_STANDARD_MODES)


def test_compatibility_policy_preserves_unknown_future_mode() -> None:
    """Verify a valid future policy mode remains exact and distinguishable."""
    identifier = OpenIdentifier("vendor.audit_compatible")
    policy = CompatibilityPolicy(identifier)

    # Unknown modes retain their nominal identifier instance and are never
    # coerced to compatible, permissive, or a generic unknown sentinel.
    assert policy.mode is identifier
    assert str(policy) == "vendor.audit_compatible"
    assert policy not in {
        CompatibilityPolicy(OpenIdentifier(mode)) for mode in _STANDARD_MODES
    }


def test_compatibility_policy_round_trips_unknown_mode_through_json() -> None:
    """Verify ordinary value serialization preserves an unknown mode exactly."""
    policy = CompatibilityPolicy(OpenIdentifier("vendor.audit_compatible"))

    # Serialize only the public mode text and reconstruct through the same
    # validated constructor path used by standard modes.
    encoded = json.dumps({"mode": str(policy)})
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = CompatibilityPolicy(OpenIdentifier(decoded["mode"]))

    assert restored == policy
    assert str(restored) == "vendor.audit_compatible"


def test_compatibility_policy_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability use the open mode identifier."""
    first = CompatibilityPolicy(OpenIdentifier("strict"))
    same = CompatibilityPolicy(OpenIdentifier("strict"))
    different = CompatibilityPolicy(OpenIdentifier("compatible"))

    # Frozen value semantics make policies safe configuration inputs without
    # introducing shared mutable behavior or a mode registry.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("strict")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("mode", OpenIdentifier("compatible")),
        "cannot assign to field",
    )


def test_compatibility_policy_rejects_invalid_open_modes() -> None:
    """Verify every policy mode obeys the portable identifier grammar."""
    for value in ("", "Strict", "compatible mode", "vendor/mode"):
        # Each invalid value reaches the shared OpenIdentifier validator, which
        # produces the same cross-domain syntax diagnostics.
        _assert_raises(
            ValueError,
            lambda value=value: CompatibilityPolicy(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_compatibility_policy_requires_open_identifier() -> None:
    """Verify dynamic callers cannot replace the nominal mode value type."""
    # Rejecting raw strings keeps policy construction on the same validated open
    # value path used throughout the domain package.
    _assert_raises(
        TypeError,
        lambda: CompatibilityPolicy(cast(OpenIdentifier, "strict")),
        "mode must be an OpenIdentifier",
    )
