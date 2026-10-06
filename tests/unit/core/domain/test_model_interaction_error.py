"""Field and exception tests for ModelInteractionError."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import (
    Duration,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
    RecoveryHint,
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


def _category(value: str = "network") -> ErrorCategory:
    """Build a valid category used by error field tests."""
    return ErrorCategory(OpenIdentifier(value))


def _phase(value: str = "transport") -> InteractionPhase:
    """Build a valid phase used by error field tests."""
    return InteractionPhase(OpenIdentifier(value))


def test_model_interaction_error_preserves_complete_fields() -> None:
    """Verify normalized, service, recovery, and cause fields remain distinct."""
    cause = OSError("connection closed")
    recovery = RecoveryHint(
        transient=True,
        retry_after=Duration(1_000_000_000),
        request_may_have_been_processed=True,
    )
    error = ModelInteractionError(
        category=_category(),
        phase=_phase(),
        code="connection_lost",
        message="The model service connection closed.",
        status_code=503,
        service_error_code="upstream_unavailable",
        request_id="request-placeholder",
        recovery=recovery,
        cause=cause,
    )

    assert error.category == _category()
    assert error.phase == _phase()
    assert error.code == "connection_lost"
    assert error.status_code == 503
    assert error.service_error_code == "upstream_unavailable"
    assert error.request_id == "request-placeholder"
    assert error.recovery is recovery
    assert error.cause is cause
    assert error.__cause__ is cause
    assert error.args == ("The model service connection closed.",)
    assert str(error) == "The model service connection closed."


def test_model_interaction_error_supports_minimal_normalized_failure() -> None:
    """Verify optional service, recovery, and cause fields default to absent."""
    error = ModelInteractionError(
        _category("invalid_request"),
        _phase("validation"),
        "invalid_model_descriptor",
        "The model descriptor is invalid.",
    )

    assert error.status_code is None
    assert error.service_error_code is None
    assert error.request_id is None
    assert error.recovery is None
    assert error.cause is None
    assert error.__cause__ is None


def test_model_interaction_error_can_be_raised_and_caught() -> None:
    """Verify the normalized value participates in Python exception handling."""
    error = ModelInteractionError(
        _category("timeout"),
        _phase(),
        "request_timeout",
        "The request timed out.",
    )

    try:
        raise error
    except ModelInteractionError as caught:
        assert caught is error
        assert caught.code == "request_timeout"


def test_model_interaction_error_is_immutable() -> None:
    """Verify normalized fields cannot change after construction."""
    error = ModelInteractionError(
        _category(),
        _phase(),
        "connection_lost",
        "The connection closed.",
    )

    _assert_raises(
        FrozenInstanceError,
        lambda: error.__setattr__("code", "changed"),
        "cannot assign to field",
    )


def test_model_interaction_error_rejects_invalid_required_fields() -> None:
    """Verify required fields keep nominal and scalar type boundaries."""
    valid = (_category(), _phase(), "code", "message")

    _assert_raises(
        TypeError,
        lambda: ModelInteractionError(
            cast(ErrorCategory, "network"),
            valid[1],
            valid[2],
            valid[3],
        ),
        "category must be an ErrorCategory",
    )
    _assert_raises(
        TypeError,
        lambda: ModelInteractionError(
            valid[0],
            cast(InteractionPhase, "transport"),
            valid[2],
            valid[3],
        ),
        "phase must be an InteractionPhase",
    )
    _assert_raises(
        TypeError,
        lambda: ModelInteractionError(valid[0], valid[1], cast(str, 1), valid[3]),
        "code must be a string",
    )


def test_model_interaction_error_rejects_invalid_optional_fields() -> None:
    """Verify optional fields cannot use truthy or structurally similar values."""
    category = _category()
    phase = _phase()

    _assert_raises(
        TypeError,
        lambda: ModelInteractionError(
            category,
            phase,
            "code",
            "message",
            status_code=cast(int, True),
        ),
        "status_code must be an integer or None",
    )
    _assert_raises(
        TypeError,
        lambda: ModelInteractionError(
            category,
            phase,
            "code",
            "message",
            recovery=cast(RecoveryHint, {}),
        ),
        "recovery must be a RecoveryHint or None",
    )
    _assert_raises(
        TypeError,
        lambda: ModelInteractionError(
            category,
            phase,
            "code",
            "message",
            cause=cast(BaseException, "failure"),
        ),
        "cause must be a BaseException or None",
    )
