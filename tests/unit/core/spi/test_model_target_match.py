"""Value and boundary tests for immutable model target match outcomes."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Diagnostic, InteractionPhase, OpenIdentifier
from mconet.core.spi import ModelTargetMatch


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match outcome-owned wording so malformed fixture construction cannot
        # accidentally satisfy a negative match-boundary test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _diagnostic(code: str) -> Diagnostic:
    """Build one non-sensitive target-matching diagnostic with a unique code."""
    # Distinct codes make tuple ordering observable without introducing matcher
    # behavior or target-specific data into this value-object test.
    return Diagnostic(
        code=code,
        severity="info",
        phase=InteractionPhase(OpenIdentifier("integration_resolution")),
        message="Model target matching completed.",
    )


def test_model_target_match_preserves_decision_score_and_diagnostics() -> None:
    """Verify every target-matching fact remains exact and ordered."""
    first = _diagnostic("service_matched")
    second = _diagnostic("protocol_matched")

    result = ModelTargetMatch(True, 400, (first, second))

    # The value reports facts without recalculating the matcher-owned score or
    # sorting, merging, or copying the ordered diagnostic observations.
    assert result.matched is True
    assert result.score == 400
    assert result.diagnostics == (first, second)
    assert result.diagnostics[0] is first
    assert result.diagnostics[1] is second


def test_model_target_match_represents_non_matches_and_open_scores() -> None:
    """Verify false decisions and arbitrary signed integer scales remain expressible."""
    no_match = ModelTargetMatch(False, -1)
    large_score = ModelTargetMatch(True, 1 << 80)

    # This data carrier does not invent a score range or force false matches to
    # zero; deterministic ranking and consistency policy belong to the resolver.
    assert no_match.matched is False
    assert no_match.score == -1
    assert no_match.diagnostics == ()
    assert large_score.score == 1 << 80


def test_model_target_match_has_frozen_exact_field_surface() -> None:
    """Verify the outcome exposes only decision, score, and diagnostics."""
    result = ModelTargetMatch(True, 10)

    # Target input and matcher identity remain owned by resolver orchestration;
    # this result contains only the three facts required for candidate handling.
    assert tuple(field.name for field in fields(ModelTargetMatch)) == (
        "matched",
        "score",
        "diagnostics",
    )
    assert not hasattr(result, "target")
    assert not hasattr(result, "matcher")
    assert not hasattr(result, "component")
    _assert_raises(
        FrozenInstanceError,
        lambda: result.__setattr__("score", 11),
        "cannot assign to field",
    )


def test_model_target_match_has_value_equality() -> None:
    """Verify identical immutable facts compare equally without hidden state."""
    diagnostic = _diagnostic("matched")
    first = ModelTargetMatch(True, 20, (diagnostic,))
    same = ModelTargetMatch(True, 20, (diagnostic,))
    different = ModelTargetMatch(False, 20, (diagnostic,))

    # Equality includes all declared fields and no matcher instance, target
    # identity, registration order, or runtime state outside the data record.
    assert first == same
    assert first != different


def test_model_target_match_requires_exact_boolean_and_integer_values() -> None:
    """Verify permissive Python numeric relationships cannot blur field meaning."""
    # bool is an int subclass in Python, so both fields use exact membership to
    # preserve a decision distinct from a numeric score across language ports.
    _assert_raises(
        TypeError,
        lambda: ModelTargetMatch(cast(bool, 1), 10),
        "matched must be a boolean",
    )
    for invalid_score in (True, 1.5, "10"):
        _assert_raises(
            TypeError,
            lambda invalid_score=invalid_score: ModelTargetMatch(
                True,
                cast(int, invalid_score),
            ),
            "score must be an integer",
        )


def test_model_target_match_requires_immutable_structured_diagnostics() -> None:
    """Verify diagnostics use tuple storage containing only Diagnostic values."""
    diagnostic = _diagnostic("matched")

    # A list could change after candidate evaluation, while arbitrary tuple items
    # would bypass severity, phase, message, and non-secret detail boundaries.
    _assert_raises(
        TypeError,
        lambda: ModelTargetMatch(
            True,
            10,
            cast(tuple[Diagnostic, ...], [diagnostic]),
        ),
        "diagnostics must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: ModelTargetMatch(
            True,
            10,
            cast(tuple[Diagnostic, ...], (object(),)),
        ),
        "diagnostics must contain Diagnostic values",
    )
