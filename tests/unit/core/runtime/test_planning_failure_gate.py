"""Planning failure does not read a credential."""

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
from mconet.core.runtime._planning_failure_gate import run_planning_gate


def test_planning_failure_does_not_read_a_credential() -> None:
    """Verify a planning error stops before the credential reader."""
    calls: list[str] = []

    def _plan() -> str:
        calls.append("plan")
        raise ModelInteractionError(
            ErrorCategory(OpenIdentifier("unsupported_feature")),
            InteractionPhase(OpenIdentifier("protocol_planning")),
            "unsupported_protocol_plan",
            "The protocol plan is outside the supported range.",
        )

    def _read_credential(plan: str) -> str:
        del plan
        calls.append("credential")
        return "credential"

    machine = InteractionTerminalMachine()
    error = _capture(lambda: run_planning_gate(_plan, _read_credential, machine))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_protocol_plan"
    assert calls == ["plan"]
    assert machine.state is not None
    assert machine.state.failed is True


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
