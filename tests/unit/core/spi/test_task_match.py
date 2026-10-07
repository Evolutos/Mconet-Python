"""Value and boundary tests for immutable task match outcomes."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Diagnostic, InteractionPhase, OpenIdentifier
from mconet.core.spi import TaskMatch


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match TaskMatch-owned wording so fixture failures cannot accidentally
        # satisfy a negative field-boundary test for another value.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _diagnostic(code: str) -> Diagnostic:
    """Build one non-sensitive task-matching diagnostic with a unique code."""
    # Distinct codes make observation order visible without embedding a task,
    # mode, matcher implementation, or resolution policy in this value test.
    return Diagnostic(
        code=code,
        severity="info",
        phase=InteractionPhase(OpenIdentifier("integration_resolution")),
        message="Task and interaction mode matching completed.",
    )


def test_task_match_preserves_decision_score_and_diagnostics() -> None:
    """Verify every task-matching fact remains exact and ordered."""
    task_diagnostic = _diagnostic("task_matched")
    mode_diagnostic = _diagnostic("mode_matched")

    result = TaskMatch(True, 200, (task_diagnostic, mode_diagnostic))

    # The result preserves matcher output without recalculating score or sorting,
    # merging, or reconstructing its task-then-mode observations.
    assert result.matched is True
    assert result.score == 200
    assert result.diagnostics == (task_diagnostic, mode_diagnostic)
    assert result.diagnostics[0] is task_diagnostic
    assert result.diagnostics[1] is mode_diagnostic


def test_task_match_represents_non_matches_and_open_scores() -> None:
    """Verify false decisions and arbitrary signed integer scales remain expressible."""
    unsupported_mode = TaskMatch(False, -5)
    large_score = TaskMatch(True, 1 << 80)

    # This carrier does not infer a decision from score, force a zero for false,
    # or impose a platform-specific integer range before resolver policy exists.
    assert unsupported_mode.matched is False
    assert unsupported_mode.score == -5
    assert unsupported_mode.diagnostics == ()
    assert large_score.score == 1 << 80


def test_task_match_has_frozen_exact_field_surface() -> None:
    """Verify the outcome exposes only decision, score, and diagnostics."""
    result = TaskMatch(True, 10)

    # TaskDescriptor, InteractionMode, matcher, and components remain owned by
    # orchestration; duplicating them here could create inconsistent snapshots.
    assert tuple(field.name for field in fields(TaskMatch)) == (
        "matched",
        "score",
        "diagnostics",
    )
    assert not hasattr(result, "task")
    assert not hasattr(result, "mode")
    assert not hasattr(result, "matcher")
    assert not hasattr(result, "component")
    _assert_raises(
        FrozenInstanceError,
        lambda: result.__setattr__("matched", False),
        "cannot assign to field",
    )


def test_task_match_has_value_equality() -> None:
    """Verify identical immutable facts compare equally without hidden state."""
    diagnostic = _diagnostic("matched")
    first = TaskMatch(True, 20, (diagnostic,))
    same = TaskMatch(True, 20, (diagnostic,))
    different = TaskMatch(True, 21, (diagnostic,))

    # Equality includes exactly the declared values and excludes matcher identity,
    # registration order, task objects, modes, and resolver runtime state.
    assert first == same
    assert first != different


def test_task_match_requires_exact_boolean_and_integer_values() -> None:
    """Verify Python numeric relationships cannot blur decision and score meaning."""
    # Both checks use exact type membership so bool cannot enter score and an int
    # cannot silently stand in for the explicit applicability decision.
    _assert_raises(
        TypeError,
        lambda: TaskMatch(cast(bool, 1), 10),
        "matched must be a boolean",
    )
    for invalid_score in (False, 1.5, "10"):
        _assert_raises(
            TypeError,
            lambda invalid_score=invalid_score: TaskMatch(
                True,
                cast(int, invalid_score),
            ),
            "score must be an integer",
        )


def test_task_match_requires_immutable_structured_diagnostics() -> None:
    """Verify diagnostics use tuple storage containing only Diagnostic values."""
    diagnostic = _diagnostic("matched")

    # A mutable list could change after evaluation, while arbitrary tuple members
    # would bypass Diagnostic phase, severity, message, and safety validation.
    _assert_raises(
        TypeError,
        lambda: TaskMatch(
            True,
            10,
            cast(tuple[Diagnostic, ...], [diagnostic]),
        ),
        "diagnostics must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: TaskMatch(
            True,
            10,
            cast(tuple[Diagnostic, ...], (object(),)),
        ),
        "diagnostics must contain Diagnostic values",
    )
