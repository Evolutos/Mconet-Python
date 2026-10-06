"""Open-value tests for immutable MonitoringMergeMode values."""

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import MonitoringMergeMode, OpenIdentifier

_STANDARD_MODES = ("append", "prepend", "replace")


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the stable domain diagnostic as well as its type so an unrelated
    # constructor failure cannot make a negative merge-mode test pass.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_monitoring_merge_mode_accepts_every_standard_value() -> None:
    """Verify append, prepend, and replace remain distinct open values."""
    modes = tuple(MonitoringMergeMode(OpenIdentifier(mode)) for mode in _STANDARD_MODES)

    # The value object records strategy identity only. A later monitoring
    # component owns the ordering and replacement behavior of each known mode.
    assert tuple(str(mode) for mode in modes) == _STANDARD_MODES
    assert len(set(modes)) == len(_STANDARD_MODES)


def test_monitoring_merge_mode_preserves_unknown_future_value() -> None:
    """Verify a valid future merge mode remains exact and distinguishable."""
    identifier = OpenIdentifier("vendor.interleave")
    mode = MonitoringMergeMode(identifier)

    # Unknown modes retain the original nominal identifier and are not replaced
    # with append, prepend, replace, or a generic unknown sentinel.
    assert mode.mode is identifier
    assert str(mode) == "vendor.interleave"
    assert mode not in {
        MonitoringMergeMode(OpenIdentifier(value)) for value in _STANDARD_MODES
    }


def test_monitoring_merge_mode_round_trips_unknown_value_through_json() -> None:
    """Verify ordinary value serialization preserves an unknown mode exactly."""
    mode = MonitoringMergeMode(OpenIdentifier("vendor.interleave"))

    # Serialize only the public identifier text and reconstruct through the same
    # validated constructor path used by every standard mode.
    encoded = json.dumps({"mode": str(mode)})
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = MonitoringMergeMode(OpenIdentifier(decoded["mode"]))

    assert restored == mode
    assert str(restored) == "vendor.interleave"


def test_monitoring_merge_mode_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability use the open mode identifier."""
    first = MonitoringMergeMode(OpenIdentifier("append"))
    same = MonitoringMergeMode(OpenIdentifier("append"))
    different = MonitoringMergeMode(OpenIdentifier("replace"))

    # Frozen value semantics make merge modes safe configuration values without
    # introducing mutable monitor state or a strategy registry.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("append")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("mode", OpenIdentifier("prepend")),
        "cannot assign to field",
    )


def test_monitoring_merge_mode_rejects_invalid_open_values() -> None:
    """Verify every merge mode obeys the portable identifier grammar."""
    for value in ("", "Append", "replace mode", "vendor/mode"):
        # Invalid standard-looking and extension values share the same open
        # identifier diagnostics instead of receiving closed-enum fallbacks.
        _assert_raises(
            ValueError,
            lambda value=value: MonitoringMergeMode(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_monitoring_merge_mode_requires_open_identifier() -> None:
    """Verify dynamic callers cannot replace the nominal mode value type."""
    # Reject raw strings so construction always passes through the shared open
    # identifier storage and validation contract.
    _assert_raises(
        TypeError,
        lambda: MonitoringMergeMode(cast(OpenIdentifier, "append")),
        "mode must be an OpenIdentifier",
    )
