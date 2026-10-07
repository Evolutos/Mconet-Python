"""Open-value tests for normalized transport outcomes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import TransportOutcome

_STANDARD_OUTCOMES = ("success", "service_error", "transport_error")


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match a stable boundary fragment so an unrelated exception cannot make
        # a negative open-value test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_transport_outcome_accepts_every_standard_value() -> None:
    """Verify all normalized standard outcomes remain distinct open values."""
    outcomes = tuple(
        TransportOutcome(OpenIdentifier(value)) for value in _STANDARD_OUTCOMES
    )

    # The three results describe transport-level facts only; each uses the same
    # open construction path available to future implementations.
    assert tuple(str(outcome) for outcome in outcomes) == _STANDARD_OUTCOMES
    assert len(set(outcomes)) == len(_STANDARD_OUTCOMES)


def test_transport_outcome_preserves_unknown_future_value() -> None:
    """Verify a valid extension outcome remains exact and distinguishable."""
    identifier = OpenIdentifier("vendor.partial_response")
    outcome = TransportOutcome(identifier)

    # Unknown values preserve both identifier identity and text instead of being
    # collapsed into transport_error or a generic unknown sentinel.
    assert outcome.id is identifier
    assert str(outcome) == "vendor.partial_response"
    assert outcome not in {
        TransportOutcome(OpenIdentifier(value)) for value in _STANDARD_OUTCOMES
    }


def test_transport_outcome_round_trips_unknown_value_through_json() -> None:
    """Verify ordinary metadata serialization preserves extension text."""
    outcome = TransportOutcome(OpenIdentifier("vendor.partial_response"))

    # Serialize only the owned identifier and reconstruct through the same open
    # constructor without a standard-value lookup or fallback substitution.
    encoded = json.dumps({"outcome": str(outcome)}, sort_keys=True)
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = TransportOutcome(OpenIdentifier(decoded["outcome"]))

    assert restored == outcome
    assert restored.id is not outcome.id
    assert str(restored) == "vendor.partial_response"


def test_transport_outcome_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability depend only on outcome ID."""
    first = TransportOutcome(OpenIdentifier("success"))
    same = TransportOutcome(OpenIdentifier("success"))
    different = TransportOutcome(OpenIdentifier("service_error"))

    # Frozen identifier semantics make normalized results safe snapshot values
    # while preventing a response from changing classification after receipt.
    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("success")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", OpenIdentifier("transport_error")),
        "cannot assign to field",
    )


def test_transport_outcome_contains_only_normalized_identity() -> None:
    """Verify native status and response data remain outside the outcome value."""
    outcome = TransportOutcome(OpenIdentifier("service_error"))

    # The one-field surface prevents this value from absorbing metadata later
    # owned by TransportResponseMetadata or the response body container.
    assert tuple(field.name for field in fields(TransportOutcome)) == ("id",)
    assert not hasattr(outcome, "status_code")
    assert not hasattr(outcome, "headers")
    assert not hasattr(outcome, "media_type")
    assert not hasattr(outcome, "body")


def test_transport_outcome_rejects_invalid_open_identifiers() -> None:
    """Verify all standard and extension outcomes use portable ID syntax."""
    for value in ("", "Service_Error", "service error", "vendor/outcome"):
        # Every malformed value reaches the shared identifier validator, keeping
        # Transport outcome syntax aligned with other cross-platform open values.
        _assert_raises(
            ValueError,
            lambda value=value: TransportOutcome(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_transport_outcome_requires_open_identifier() -> None:
    """Verify dynamic callers cannot substitute a bare string result value."""
    # Static casts cannot bypass the runtime nominal boundary; all outcomes must
    # retain the common OpenIdentifier value contract.
    _assert_raises(
        TypeError,
        lambda: TransportOutcome(cast(OpenIdentifier, "success")),
        "id must be an OpenIdentifier",
    )
