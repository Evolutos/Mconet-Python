"""Composition tests for immutable model integration match outcomes."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import Diagnostic, InteractionPhase, OpenIdentifier
from mconet.core.spi import ModelIntegrationMatch, ModelTargetMatch, TaskMatch


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match composition-owned wording so malformed nested fixtures cannot
        # accidentally satisfy a nominal position test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _diagnostic(code: str) -> Diagnostic:
    """Build one non-sensitive integration-matching diagnostic."""
    # A unique code makes ownership by the target or task result observable
    # without adding aggregate diagnostic behavior to the composition itself.
    return Diagnostic(
        code=code,
        severity="info",
        phase=InteractionPhase(OpenIdentifier("integration_resolution")),
        message="Integration matching completed.",
    )


def test_model_integration_match_preserves_target_task_and_mode_facts() -> None:
    """Verify both nominal results and all nested facts remain independently visible."""
    target_diagnostic = _diagnostic("target_matched")
    task_mode_diagnostic = _diagnostic("task_mode_matched")
    target = ModelTargetMatch(True, 400, (target_diagnostic,))
    task = TaskMatch(True, 200, (task_mode_diagnostic,))

    result = ModelIntegrationMatch(target, task)

    # Identity preservation keeps target and task/mode scores and observations
    # separate, without recomputing an aggregate or concatenating diagnostics.
    assert result.target is target
    assert result.task is task
    assert result.target.matched is True
    assert result.target.score == 400
    assert result.target.diagnostics == (target_diagnostic,)
    assert result.task.matched is True
    assert result.task.score == 200
    assert result.task.diagnostics == (task_mode_diagnostic,)


def test_model_integration_match_preserves_partial_match_results() -> None:
    """Verify composition does not discard or rewrite independent decisions."""
    target = ModelTargetMatch(True, 100)
    unsupported_task_mode = TaskMatch(False, -1, (_diagnostic("mode_unsupported"),))

    result = ModelIntegrationMatch(target, unsupported_task_mode)

    # A resolver may need both facts to explain candidate rejection. The data
    # carrier therefore does not infer an aggregate matched flag or zero scores.
    assert result.target.matched is True
    assert result.target.score == 100
    assert result.task.matched is False
    assert result.task.score == -1
    assert result.task.diagnostics[0].code == "mode_unsupported"
    assert not hasattr(result, "matched")
    assert not hasattr(result, "score")
    assert not hasattr(result, "diagnostics")


def test_model_integration_match_has_frozen_exact_field_surface() -> None:
    """Verify only target and task-and-mode results form the composition."""
    result = ModelIntegrationMatch(ModelTargetMatch(True, 1), TaskMatch(True, 1))

    # InteractionMode is already represented within TaskMatch, so a second mode
    # field or copied specificity values would create two sources of truth.
    assert tuple(field.name for field in fields(ModelIntegrationMatch)) == (
        "target",
        "task",
    )
    assert not hasattr(result, "mode")
    assert not hasattr(result, "task_specificity")
    assert not hasattr(result, "mode_specificity")
    assert not hasattr(result, "binding")
    _assert_raises(
        FrozenInstanceError,
        lambda: result.__setattr__("task", TaskMatch(False, 0)),
        "cannot assign to field",
    )


def test_model_integration_match_has_value_equality() -> None:
    """Verify equality contains both nested outcomes and no hidden resolver state."""
    target = ModelTargetMatch(True, 10)
    task = TaskMatch(True, 20)
    first = ModelIntegrationMatch(target, task)
    same = ModelIntegrationMatch(target, task)
    different = ModelIntegrationMatch(target, TaskMatch(False, 20))

    # Dataclass equality composes nested value equality without observing binding
    # identity, candidate order, resolver configuration, or mutable runtime state.
    assert first == same
    assert first != different


def test_model_integration_match_requires_nominal_results_in_each_position() -> None:
    """Verify structurally similar match types cannot be swapped or replaced."""
    target = ModelTargetMatch(True, 10)
    task = TaskMatch(True, 20)

    # Both nested types expose matched/score/diagnostics, but their positions are
    # semantically distinct and must remain nominally checked at runtime.
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationMatch(cast(ModelTargetMatch, task), task),
        "target must be a ModelTargetMatch",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationMatch(target, cast(TaskMatch, target)),
        "task must be a TaskMatch",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationMatch(cast(ModelTargetMatch, object()), task),
        "target must be a ModelTargetMatch",
    )
    _assert_raises(
        TypeError,
        lambda: ModelIntegrationMatch(target, cast(TaskMatch, object())),
        "task must be a TaskMatch",
    )
