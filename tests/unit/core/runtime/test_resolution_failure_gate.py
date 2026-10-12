"""Resolution failure terminates once and does not plan."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)
from mconet.core.runtime._resolution_failure_gate import run_resolution_gate


def test_resolution_failure_terminates_once_and_skips_planning() -> None:
    """Verify planning does not start and a second termination is rejected."""
    calls: list[str] = []

    def _resolve() -> str:
        calls.append("resolve")
        raise ModelInteractionError(
            ErrorCategory(OpenIdentifier("invalid_request")),
            InteractionPhase(OpenIdentifier("service_access_resolution")),
            "missing_authorization",
            "Service access has no authorization.",
        )

    def _plan(access: str) -> str:
        del access
        calls.append("plan")
        return "planned"

    machine = InteractionTerminalMachine()
    error = _capture(lambda: run_resolution_gate(_resolve, _plan, machine))
    repeated = _capture(machine.fail)

    assert isinstance(error, ModelInteractionError)
    assert error.code == "missing_authorization"
    assert calls == ["resolve"]
    assert machine.state is not None
    assert machine.state.failed is True
    assert isinstance(repeated, ModelInteractionError)
    assert repeated.code == "interaction_already_terminal"


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
