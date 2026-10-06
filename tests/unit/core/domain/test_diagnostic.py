"""Field-contract tests for immutable Diagnostic records."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import Literal, TypeAlias, cast

from mconet.core.domain import (
    Diagnostic,
    InteractionPhase,
    JsonValue,
    OpenIdentifier,
)

_DiagnosticSeverity: TypeAlias = Literal["info", "warning", "error"]


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


def test_diagnostic_preserves_complete_structured_context() -> None:
    """Verify every contract field retains its exact typed value."""
    phase = InteractionPhase(OpenIdentifier("protocol_adaptation"))
    service_id = OpenIdentifier("vendor.model-service")
    details: JsonValue = {
        "sourceKind": "content.future",
        "supported": ["content.text", "content.json"],
        "lossy": False,
    }
    diagnostic = Diagnostic(
        code="unsupported_message_content",
        severity="warning",
        phase=phase,
        message="A future content kind was retained without interpretation.",
        path="/task/document/root/content/0",
        service_id=service_id,
        details=details,
    )

    assert diagnostic.code == "unsupported_message_content"
    assert diagnostic.severity == "warning"
    assert diagnostic.phase is phase
    assert diagnostic.path == "/task/document/root/content/0"
    assert diagnostic.service_id is service_id
    assert diagnostic.details == details


def test_diagnostic_accepts_all_severities_and_optional_fields() -> None:
    """Verify severity is closed while path, service, and details may be absent."""
    phase = InteractionPhase(OpenIdentifier("validation"))
    severities: tuple[_DiagnosticSeverity, ...] = ("info", "warning", "error")

    diagnostics = tuple(
        Diagnostic("validation_result", severity, phase, "Validation completed.")
        for severity in severities
    )

    assert tuple(item.severity for item in diagnostics) == severities
    assert all(item.path is None for item in diagnostics)
    assert all(item.service_id is None for item in diagnostics)
    assert all(item.details is None for item in diagnostics)


def test_diagnostic_is_immutable_and_has_value_equality() -> None:
    """Verify records compare by fields and cannot be reassigned."""
    phase = InteractionPhase(OpenIdentifier("validation"))
    first = Diagnostic("invalid_value", "error", phase, "Value is invalid.")
    same = Diagnostic("invalid_value", "error", phase, "Value is invalid.")

    assert first == same
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("severity", "warning"),
        "cannot assign to field",
    )


def test_diagnostic_rejects_invalid_scalar_fields() -> None:
    """Verify dynamic callers cannot bypass scalar and nominal field types."""
    phase = InteractionPhase(OpenIdentifier("validation"))

    _assert_raises(
        TypeError,
        lambda: Diagnostic(cast(str, 1), "info", phase, "message"),
        "code must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: Diagnostic("code", cast(_DiagnosticSeverity, 1), phase, "message"),
        "severity must be a string",
    )
    _assert_raises(
        ValueError,
        lambda: Diagnostic(
            "code",
            cast(_DiagnosticSeverity, "fatal"),
            phase,
            "message",
        ),
        "must be info, warning, or error",
    )
    _assert_raises(
        TypeError,
        lambda: Diagnostic(
            "code",
            "info",
            cast(InteractionPhase, "phase"),
            "message",
        ),
        "phase must be an InteractionPhase",
    )


def test_diagnostic_rejects_invalid_optional_fields() -> None:
    """Verify optional path, service, and detail values retain their contracts."""
    phase = InteractionPhase(OpenIdentifier("validation"))

    _assert_raises(
        TypeError,
        lambda: Diagnostic("code", "info", phase, "message", path=cast(str, 1)),
        "path must be a string or None",
    )
    _assert_raises(
        TypeError,
        lambda: Diagnostic(
            "code",
            "info",
            phase,
            "message",
            service_id=cast(OpenIdentifier, "service"),
        ),
        "service_id must be an OpenIdentifier or None",
    )
    _assert_raises(
        TypeError,
        lambda: Diagnostic(
            "code",
            "info",
            phase,
            "message",
            details=cast(JsonValue, ("not", "json")),
        ),
        "details must be a JsonValue or None",
    )


def test_diagnostic_rejects_invalid_recursive_json_details() -> None:
    """Verify non-string object keys and cyclic containers are not JSON values."""
    invalid_key = cast(JsonValue, {1: "value"})
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)

    phase = InteractionPhase(OpenIdentifier("validation"))
    for details in (invalid_key, cyclic):
        _assert_raises(
            TypeError,
            lambda details=details: Diagnostic(
                "code",
                "warning",
                phase,
                "message",
                details=details,
            ),
            "details must be a JsonValue or None",
        )
