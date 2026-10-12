"""Tests for the unknown interaction exception boundary."""

from __future__ import annotations

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._unknown_exception_boundary import guard_unknown_exception


def test_known_interaction_error_is_preserved() -> None:
    """Verify a normalized error is not wrapped again."""
    expected = ModelInteractionError(
        ErrorCategory(OpenIdentifier("protocol")),
        InteractionPhase(OpenIdentifier("decoding")),
        "payload_decoding_failed",
        "The response payload could not be decoded.",
    )
    calls = 0

    def _fail() -> None:
        nonlocal calls
        calls += 1
        raise expected

    try:
        guard_unknown_exception(
            _fail,
            phase=InteractionPhase(OpenIdentifier("decoding")),
        )
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected the known error.")

    assert raised is expected
    assert calls == 1


def test_unknown_exception_keeps_cause_and_hides_its_text() -> None:
    """Verify the public message omits a secret carried by the cause."""
    phase = InteractionPhase(OpenIdentifier("transport"))
    cause = RuntimeError("mconet-test-bearer-token-not-secret")

    def _fail() -> str:
        raise cause

    try:
        guard_unknown_exception(_fail, phase=phase)
    except ModelInteractionError as error:
        raised = error
    else:
        raise AssertionError("Expected an unknown failure.")

    assert raised.code == "unknown_interaction_failure"
    assert raised.category == ErrorCategory(OpenIdentifier("internal"))
    assert raised.phase == phase
    assert raised.cause is cause
    assert raised.__cause__ is cause
    assert "mconet-test-bearer-token-not-secret" not in raised.message
    assert "mconet-test-bearer-token-not-secret" not in str(raised)


def test_successful_result_is_returned() -> None:
    """Verify a completed step is not converted into an error."""
    assert (
        guard_unknown_exception(
            lambda: "ready",
            phase=InteractionPhase(OpenIdentifier("validation")),
        )
        == "ready"
    )


def test_keyboard_interrupt_is_not_normalized() -> None:
    """Verify process interruption stays outside the interaction error."""

    def _interrupt() -> None:
        raise KeyboardInterrupt

    try:
        guard_unknown_exception(
            _interrupt,
            phase=InteractionPhase(OpenIdentifier("transport")),
        )
    except KeyboardInterrupt:
        return
    raise AssertionError("Expected KeyboardInterrupt.")
