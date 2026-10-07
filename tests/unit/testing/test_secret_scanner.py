"""Leak detection, diagnostic safety, and carrier tests for SecretScanner."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import (
    Bytes,
    ErrorCategory,
    HeaderField,
    Headers,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi import TransportBody
from mconet.testing import SecretScanner

_PROTECTED_PLAINTEXT = "-".join(("runtime", "private", "marker"))


def _assert_leak(carrier: object) -> str:
    """Return a leak diagnostic while proving it never echoes plaintext."""
    try:
        SecretScanner().assert_absent(_PROTECTED_PLAINTEXT, carrier)
    except AssertionError as error:
        # Only structural coordinates may escape from a failed security check.
        message = str(error)
        assert "Secret detected in an inspected carrier." in message
        assert _PROTECTED_PLAINTEXT not in message
        assert error.__cause__ is None
        return message
    raise AssertionError("Expected protected plaintext to be detected.")


def test_scanner_accepts_clean_header_body_error_snapshot_and_log_carriers() -> None:
    """Accept already-redacted representations across required carrier kinds."""
    headers = Headers((HeaderField("Authorization", "Bearer [REDACTED]"),))
    body = TransportBody(Bytes(b"body=[REDACTED]"), MediaType("application", "json"))
    error = RuntimeError("Authorization failed for [REDACTED]")
    snapshot = {"phase": "authorization", "credential": "[REDACTED]"}
    logs = ["request started", "authorization=[REDACTED]"]

    # Actual SDK dataclass carriers exercise native slot reads, while ordinary
    # dictionaries and lists model monitoring snapshots and captured log output.
    assert (
        SecretScanner().assert_absent(
            _PROTECTED_PLAINTEXT,
            headers,
            body,
            error,
            snapshot,
            logs,
        )
        is None
    )


def test_scanner_locates_header_body_error_and_log_plaintext_without_echoing() -> None:
    """Detect the known plaintext in every required observable carrier."""
    carriers: tuple[object, ...] = (
        [{"name": "Authorization", "value": f"Bearer {_PROTECTED_PLAINTEXT}"}],
        b"prefix\xff" + _PROTECTED_PLAINTEXT.encode() + b"\xfesuffix",
        RuntimeError(f"Authorization failed: {_PROTECTED_PLAINTEXT}"),
        [f"request credential={_PROTECTED_PLAINTEXT}"],
    )

    messages = tuple(_assert_leak(carrier) for carrier in carriers)

    # Locations identify header structure, bytes, error arguments, and logs
    # without copying the matched value into diagnostic text.
    assert "mappingValue" in messages[0]
    assert "carrier[0]" in messages[1]
    assert "exceptionArguments" in messages[2]
    assert "sequenceValue" in messages[3]


def test_scanner_checks_mapping_keys_sets_and_nested_dataclass_fields() -> None:
    """Inspect all observable data positions rather than values alone."""

    @dataclass(frozen=True, slots=True)
    class Carrier:
        """Provide one native slotted field for scanner coverage."""

        payload: object

    carriers = (
        {_PROTECTED_PLAINTEXT: "[REDACTED]"},
        {"credential": {_PROTECTED_PLAINTEXT}},
        Carrier({"nested": _PROTECTED_PLAINTEXT}),
    )

    messages = tuple(_assert_leak(carrier) for carrier in carriers)

    assert "mappingKey" in messages[0]
    assert "setValue" in messages[1]
    assert "fieldValue" in messages[2]


def test_scanner_checks_exception_cause_context_and_custom_state() -> None:
    """Traverse error chains and stored diagnostic data without stringifying."""
    caused = RuntimeError("outer")
    caused.__cause__ = ValueError(_PROTECTED_PLAINTEXT)
    contextual = RuntimeError("outer")
    contextual.__context__ = ValueError(_PROTECTED_PLAINTEXT)
    stateful = RuntimeError("outer")
    stateful.__dict__["detail"] = {"credential": _PROTECTED_PLAINTEXT}
    normalized = ModelInteractionError(
        ErrorCategory(OpenIdentifier("network")),
        InteractionPhase(OpenIdentifier("transport")),
        "connection_lost",
        "Connection failed.",
        request_id=_PROTECTED_PLAINTEXT,
    )

    cause_message = _assert_leak(caused)
    context_message = _assert_leak(contextual)
    state_message = _assert_leak(stateful)
    normalized_message = _assert_leak(normalized)

    assert "exceptionCause" in cause_message
    assert "exceptionContext" in context_message
    assert "exceptionState" in state_message
    assert "exceptionFields.fieldValue" in normalized_message


def test_scanner_terminates_on_repeated_cyclic_and_deep_clean_data() -> None:
    """Handle shared references, cycles, and deep carriers iteratively."""
    shared: dict[str, object] = {"value": "[REDACTED]"}
    cyclic: dict[str, object] = {"shared": shared}
    cyclic["self"] = cyclic
    deep: object = "[REDACTED]"
    for _ in range(2_000):
        # Iterative construction and scanning prove no recursion-depth coupling.
        deep = [deep]

    assert (
        SecretScanner().assert_absent(
            _PROTECTED_PLAINTEXT,
            {"first": shared, "second": shared, "cyclic": cyclic},
            deep,
        )
        is None
    )


def test_scanner_fails_closed_without_invoking_custom_representation() -> None:
    """Reject opaque objects without executing their string or property hooks."""

    class OpaqueCarrier:
        """Expose hooks that a safe scanner must never evaluate."""

        __slots__ = ("property_called", "str_called")

        def __init__(self) -> None:
            """Initialize observable hook-call flags."""
            self.str_called = False
            self.property_called = False

        @property
        def credential(self) -> str:
            """Return protected text only if an unsafe scanner invokes it."""
            self.property_called = True
            return _PROTECTED_PLAINTEXT

        def __str__(self) -> str:
            """Return protected text only if an unsafe scanner stringifies it."""
            self.str_called = True
            return _PROTECTED_PLAINTEXT

    carrier = OpaqueCarrier()

    try:
        SecretScanner().assert_absent(_PROTECTED_PLAINTEXT, carrier)
    except TypeError as error:
        # The failure uses implementation text and retains no user exception.
        assert "object type is not a supported data carrier" in str(error)
        assert _PROTECTED_PLAINTEXT not in str(error)
        assert error.__cause__ is None
    else:
        raise AssertionError("Expected opaque carrier scanning to fail closed.")

    assert not carrier.str_called
    assert not carrier.property_called


def test_scanner_bypasses_exception_attribute_overrides() -> None:
    """Inspect native error data without calling hostile subclass hooks."""

    class HostileError(RuntimeError):
        """Raise protected text if ordinary attribute dispatch occurs."""

        __slots__ = ()

        def __getattribute__(self, name: str) -> object:
            """Reject every ordinary instance attribute read."""
            del name
            raise AssertionError(_PROTECTED_PLAINTEXT)

    # Native BaseException descriptors expose the safe stored message and state
    # directly, so the hostile override is neither called nor retained.
    assert (
        SecretScanner().assert_absent(
            _PROTECTED_PLAINTEXT,
            HostileError("safe failure"),
        )
        is None
    )


def test_scanner_rejects_invalid_or_vacuous_inputs() -> None:
    """Reject an empty or non-string marker and an empty carrier collection."""
    scanner = SecretScanner()

    for invalid in ("", 42, b"marker"):
        try:
            scanner.assert_absent(cast(str, invalid), "safe")
        except TypeError as error:
            assert str(error) == "secret must be a non-empty string."
        else:
            raise AssertionError("Expected invalid protected plaintext to fail.")

    try:
        scanner.assert_absent(_PROTECTED_PLAINTEXT)
    except TypeError as error:
        assert str(error) == "at least one carrier must be provided for scanning."
    else:
        raise AssertionError("Expected an empty carrier collection to fail.")


def test_scanner_is_stateless_and_exposes_one_synchronous_operation() -> None:
    """Keep secret retention, heuristics, redaction, and history out of scope."""
    scanner = SecretScanner()
    operation = SecretScanner.assert_absent
    signature = inspect.signature(operation)

    assert tuple(signature.parameters) == ("self", "secret", "carriers")
    assert signature.parameters["secret"].annotation == "str"
    assert signature.parameters["carriers"].annotation == "object"
    assert signature.return_annotation == "None"
    assert not inspect.iscoroutinefunction(operation)
    assert not hasattr(scanner, "__dict__")

    # The scanner verifies known test plaintext only and cannot become a secret
    # store, heuristic repository scanner, redactor, serializer, or history log.
    for forbidden_member in (
        "scan_patterns",
        "redact",
        "serialize",
        "secrets",
        "carriers",
        "history",
        "reset",
    ):
        assert not hasattr(scanner, forbidden_member)
