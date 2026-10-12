"""Encoding failure does not call an authorization handler."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._encoding_failure_gate import run_encoding_gate
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)


def test_encoding_failure_does_not_authorize() -> None:
    """Verify an encoding error stops before the authorization handler."""
    calls: list[str] = []

    def _encode() -> str:
        calls.append("encode")
        raise ModelInteractionError(
            ErrorCategory(OpenIdentifier("protocol")),
            InteractionPhase(OpenIdentifier("encoding")),
            "payload_encoding_failed",
            "The request payload could not be encoded.",
        )

    def _authorize(body: str) -> str:
        del body
        calls.append("authorize")
        return "authorized"

    machine = InteractionTerminalMachine()
    error = _capture(lambda: run_encoding_gate(_encode, _authorize, machine))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "payload_encoding_failed"
    assert calls == ["encode"]
    assert machine.state is not None
    assert machine.state.failed is True


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
