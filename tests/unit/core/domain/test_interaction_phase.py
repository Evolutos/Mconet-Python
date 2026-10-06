"""Open-value tests for interaction phases."""

import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import InteractionPhase, OpenIdentifier

_STANDARD_PHASES = (
    "normalization",
    "validation",
    "component_resolution",
    "model_integration_resolution",
    "protocol_planning",
    "capability_resolution",
    "component_type_validation",
    "artifact_resolution",
    "protocol_adaptation",
    "encoding",
    "authentication",
    "transport",
    "stream_framing",
    "stream_mapping",
    "duplex_session",
    "long_running_operation",
    "decoding",
    "response_parsing",
    "monitoring",
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
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_interaction_phase_accepts_every_standard_phase() -> None:
    """Verify every normalized interaction phase is a valid stable identifier."""
    phases = tuple(
        InteractionPhase(OpenIdentifier(value)) for value in _STANDARD_PHASES
    )

    assert tuple(str(phase) for phase in phases) == _STANDARD_PHASES


def test_interaction_phase_preserves_unknown_future_phases() -> None:
    """Verify a valid phase introduced by an integration remains exact."""
    identifier = OpenIdentifier("vendor.future_validation")
    phase = InteractionPhase(identifier)

    assert phase.id is identifier
    assert str(phase) == "vendor.future_validation"
    assert phase not in {
        InteractionPhase(OpenIdentifier(value)) for value in _STANDARD_PHASES
    }


def test_interaction_phase_round_trips_unknown_value_through_json() -> None:
    """Verify wire serialization never replaces an unknown phase."""
    phase = InteractionPhase(OpenIdentifier("vendor.future_validation"))

    # The open identifier itself is the wire value, so older readers preserve
    # extensions without mapping them to a generic or known phase.
    encoded = json.dumps({"phase": str(phase)})
    decoded = cast(dict[str, str], json.loads(encoded))
    restored = InteractionPhase(OpenIdentifier(decoded["phase"]))

    assert restored == phase
    assert str(restored) == "vendor.future_validation"


def test_interaction_phase_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability use the open identifier."""
    first = InteractionPhase(OpenIdentifier("encoding"))
    same = InteractionPhase(OpenIdentifier("encoding"))
    different = InteractionPhase(OpenIdentifier("transport"))

    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != OpenIdentifier("encoding")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("id", OpenIdentifier("transport")),
        "cannot assign to field",
    )


def test_interaction_phase_rejects_invalid_identifiers() -> None:
    """Verify phase IDs satisfy the portable open-identifier contract."""
    for value in ("", "Response_Parsing", "response parsing", "response/parsing"):
        _assert_raises(
            ValueError,
            lambda value=value: InteractionPhase(OpenIdentifier(value)),
            "OpenIdentifier",
        )


def test_interaction_phase_requires_open_identifier() -> None:
    """Verify dynamic callers cannot replace the nominal identifier type."""
    _assert_raises(
        TypeError,
        lambda: InteractionPhase(cast(OpenIdentifier, "validation")),
        "id must be an OpenIdentifier",
    )
