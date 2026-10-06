"""Open-value tests for model output statuses."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier, OutputStatus

_STANDARD_STATUSES = (
    "completed",
    "requires_action",
    "incomplete",
    "refused",
    "filtered",
    "cancelled",
    "failed",
    "unknown",
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Centralized exception checks keep each test focused on one value invariant
    # while still verifying the stable public diagnostic text.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_output_status_accepts_every_standard_status() -> None:
    """Verify all documented statuses use valid, distinct open identifiers."""
    statuses = tuple(
        OutputStatus(OpenIdentifier(value)) for value in _STANDARD_STATUSES
    )

    # Standard membership is documented rather than constructor-gated, so every
    # value follows the same immutable path used by future status identifiers.
    assert tuple(str(status) for status in statuses) == _STANDARD_STATUSES
    assert len(set(statuses)) == len(_STANDARD_STATUSES)


def test_output_status_preserves_unknown_future_status() -> None:
    """Verify a provider-defined status remains exact instead of being collapsed."""
    identifier = OpenIdentifier("vendor.awaiting_review")
    status = OutputStatus(identifier)

    # The exact identifier and object identity survive construction; the standard
    # ``unknown`` value remains a real producer status, not a fallback bucket.
    assert status.id is identifier
    assert str(status) == "vendor.awaiting_review"
    assert status != OutputStatus(OpenIdentifier("unknown"))


def test_output_status_round_trips_unknown_value_through_json() -> None:
    """Verify JSON serialization preserves extension status text losslessly."""
    status = OutputStatus(OpenIdentifier("vendor.awaiting_review"))

    # Encode only the owned identifier field, then reconstruct through the same
    # public value path without a known-status lookup or fallback substitution.
    encoded = json.dumps({"status": str(status)}, sort_keys=True)
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = OutputStatus(OpenIdentifier(decoded["status"]))

    assert restored == status
    assert restored.id is not status.id
    assert str(restored) == "vendor.awaiting_review"


def test_output_status_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability depend only on status identity."""
    first = OutputStatus(OpenIdentifier("completed"))
    same = OutputStatus(OpenIdentifier("completed"))
    different = OutputStatus(OpenIdentifier("failed"))

    # Frozen dataclass semantics make statuses safe dictionary keys and prevent a
    # parsed or assembled output from changing state after construction.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("completed")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", OpenIdentifier("failed")),
        "cannot assign to field",
    )


def test_output_status_contains_only_status_identity() -> None:
    """Verify status does not absorb result, lifecycle, or failure information."""
    status = OutputStatus(OpenIdentifier("incomplete"))

    # The one-field shape keeps stop reason, task result, diagnostics, errors, and
    # protocol continuation state in their separately owned output contracts.
    assert tuple(field.name for field in fields(OutputStatus)) == ("id",)
    assert not hasattr(status, "stop_reason")
    assert not hasattr(status, "result")
    assert not hasattr(status, "diagnostics")
    assert not hasattr(status, "error")
    assert not hasattr(status, "protocol_state")


def test_output_status_rejects_invalid_identifiers() -> None:
    """Verify status identifiers satisfy the shared portable open grammar."""
    for value in ("", "Requires_Action", "requires action", "requires/action"):
        # Each malformed value reaches the shared identifier validator, ensuring
        # status syntax cannot diverge from other cross-platform open identities.
        _assert_raises(
            ValueError,
            lambda value=value: OutputStatus(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_output_status_requires_open_identifier() -> None:
    """Verify dynamic callers cannot substitute a bare string status value."""
    # An explicit cast crosses static typing only for runtime invariant coverage;
    # construction must still reject the alternate primitive representation.
    _assert_raises(
        TypeError,
        lambda: OutputStatus(cast(OpenIdentifier, "completed")),
        "id must be an OpenIdentifier",
    )
