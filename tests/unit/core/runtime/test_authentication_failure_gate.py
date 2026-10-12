"""Authentication failure does not send or expose a secret."""

from __future__ import annotations

from collections.abc import Callable

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._authentication_failure_gate import run_authentication_gate
from mconet.core.runtime._interaction_terminal_machine import (
    InteractionTerminalMachine,
)

_BEARER = "mconet-test-bearer-token-not-secret"


def test_unknown_authentication_failure_hides_secret_and_skips_transport() -> None:
    """Verify transport stays idle and the public message omits the cause text."""
    calls: list[str] = []

    def _authenticate() -> str:
        calls.append("authenticate")
        raise RuntimeError(_BEARER)

    def _send(request: str) -> str:
        del request
        calls.append("send")
        return "sent"

    machine = InteractionTerminalMachine()
    error = _capture(lambda: run_authentication_gate(_authenticate, _send, machine))

    assert isinstance(error, ModelInteractionError)
    assert error.code == "authentication_failed"
    assert _BEARER not in error.message
    assert _BEARER not in str(error)
    assert isinstance(error.cause, RuntimeError)
    assert calls == ["authenticate"]
    assert machine.state is not None
    assert machine.state.failed is True


def test_known_authentication_error_is_preserved() -> None:
    """Verify a handler error is not wrapped and still skips transport."""
    expected = ModelInteractionError(
        ErrorCategory(OpenIdentifier("invalid_request")),
        InteractionPhase(OpenIdentifier("authentication")),
        "invalid_authorization_header_name",
        "Authorization header name is not an HTTP token.",
    )
    calls: list[str] = []

    def _authenticate() -> str:
        calls.append("authenticate")
        raise expected

    def _send(request: str) -> str:
        del request
        calls.append("send")
        return "sent"

    machine = InteractionTerminalMachine()
    error = _capture(lambda: run_authentication_gate(_authenticate, _send, machine))

    assert error is expected
    assert calls == ["authenticate"]
    assert machine.state is not None
    assert machine.state.failed is True


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")
