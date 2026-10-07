"""Independent disclosure-path tests for SecretContractSuite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast

from mconet.testing import SecretContractSuite

_KNOWN_PLAINTEXT = "-".join(("contract", "private", "marker"))


def _assert_leak(
    action: Callable[[SecretContractSuite], None],
    suite: SecretContractSuite,
) -> str:
    """Return a safe leak diagnostic from one contract assertion."""
    try:
        # Pass the shared stateless suite explicitly so every leak case uses a
        # named operation and leaves no unexecuted callback result to inspect.
        action(suite)
    except AssertionError as error:
        # Contract diagnostics must locate the carrier without repeating the
        # synthetic plaintext that caused the assertion to fail.
        message = str(error)
        assert "Secret detected in an inspected carrier." in message
        assert _KNOWN_PLAINTEXT not in message
        assert error.__cause__ is None
        return message
    raise AssertionError("Expected protected plaintext to be detected.")


def _assert_log_leak(suite: SecretContractSuite) -> None:
    """Invoke the log contract with plaintext in the second capture."""
    suite.assert_log_safe(
        _KNOWN_PLAINTEXT,
        "request started",
        {"message": f"credential={_KNOWN_PLAINTEXT}"},
    )


def _assert_exception_leak(suite: SecretContractSuite) -> None:
    """Invoke the exception contract with plaintext in chained state."""
    outer = RuntimeError("request failed")
    outer.__cause__ = ValueError(_KNOWN_PLAINTEXT)
    suite.assert_exception_safe(_KNOWN_PLAINTEXT, outer)


def _assert_serialization_leak(suite: SecretContractSuite) -> None:
    """Invoke the serialization contract with plaintext UTF-8 bytes."""
    serialized = b'{"credential":"' + _KNOWN_PLAINTEXT.encode() + b'"}'
    suite.assert_serialization_safe(_KNOWN_PLAINTEXT, serialized)


def _assert_snapshot_leak(suite: SecretContractSuite) -> None:
    """Invoke the snapshot contract with plaintext in a nested value."""
    suite.assert_snapshot_safe(
        _KNOWN_PLAINTEXT,
        {"request": {"authorization": _KNOWN_PLAINTEXT}},
    )


def test_suite_accepts_redacted_log_exception_serialization_and_snapshot() -> None:
    """Accept clean values independently across every disclosure path."""
    suite = SecretContractSuite()

    assert suite.assert_log_safe(_KNOWN_PLAINTEXT, "credential=[REDACTED]") is None
    assert (
        suite.assert_exception_safe(
            _KNOWN_PLAINTEXT,
            RuntimeError("authorization failed for [REDACTED]"),
        )
        is None
    )
    assert (
        suite.assert_serialization_safe(
            _KNOWN_PLAINTEXT,
            b'{"credential":"[REDACTED]"}',
        )
        is None
    )
    assert (
        suite.assert_snapshot_safe(
            _KNOWN_PLAINTEXT,
            {"credential": "[REDACTED]"},
        )
        is None
    )


def test_suite_detects_each_disclosure_path_without_echoing_plaintext() -> None:
    """Detect leaks independently and keep every diagnostic free of plaintext."""
    suite = SecretContractSuite()

    log_message = _assert_leak(_assert_log_leak, suite)
    exception_message = _assert_leak(_assert_exception_leak, suite)
    serialization_message = _assert_leak(_assert_serialization_leak, suite)
    snapshot_message = _assert_leak(_assert_snapshot_leak, suite)

    # Structural locations prove that each public operation delegated its exact
    # carrier rather than rendering or flattening observable test data.
    assert "carrier[1].mappingValue" in log_message
    assert "exceptionCause" in exception_message
    assert "carrier[0]" in serialization_message
    assert "mappingValue" in snapshot_message


def test_exception_contract_rejects_non_exception_carriers() -> None:
    """Keep the exception entry point specific to raised exception values."""
    suite = SecretContractSuite()

    try:
        suite.assert_exception_safe(
            _KNOWN_PLAINTEXT,
            cast(BaseException, {"message": "safe"}),
        )
    except TypeError as error:
        assert str(error) == "error must be a BaseException."
        assert error.__cause__ is None
    else:
        raise AssertionError("Expected a non-exception carrier to be rejected.")


def test_suite_preserves_scanner_input_and_fail_closed_boundaries() -> None:
    """Delegate invalid input and opaque carrier rejection without translation."""
    suite = SecretContractSuite()

    try:
        suite.assert_log_safe(_KNOWN_PLAINTEXT)
    except TypeError as error:
        assert str(error) == "at least one carrier must be provided for scanning."
    else:
        raise AssertionError("Expected an empty log capture to be rejected.")

    try:
        suite.assert_snapshot_safe("", {"credential": "safe"})
    except TypeError as error:
        assert str(error) == "secret must be a non-empty string."
    else:
        raise AssertionError("Expected an empty plaintext marker to be rejected.")

    try:
        suite.assert_serialization_safe(_KNOWN_PLAINTEXT, object())
    except TypeError as error:
        assert "object type is not a supported data carrier" in str(error)
        assert _KNOWN_PLAINTEXT not in str(error)
    else:
        raise AssertionError("Expected opaque serialization output to be rejected.")


def test_suite_is_stateless_and_exposes_four_synchronous_assertions() -> None:
    """Keep carrier production, redaction, and retained history out of scope."""
    suite = SecretContractSuite()
    expected_parameters = {
        "assert_log_safe": ("self", "secret", "entries"),
        "assert_exception_safe": ("self", "secret", "error"),
        "assert_serialization_safe": ("self", "secret", "serialized"),
        "assert_snapshot_safe": ("self", "secret", "snapshot"),
    }

    for name, parameters in expected_parameters.items():
        # Inspect each operation independently to keep the public test-kit API
        # explicit and prevent an untyped generic carrier method from replacing it.
        operation = getattr(SecretContractSuite, name)
        signature = inspect.signature(operation)
        assert tuple(signature.parameters) == parameters
        assert signature.parameters["secret"].annotation == "str"
        assert signature.return_annotation == "None"
        assert not inspect.iscoroutinefunction(operation)

    assert not hasattr(suite, "__dict__")
    for forbidden_member in (
        "redact",
        "serialize",
        "snapshot",
        "log",
        "secrets",
        "history",
        "reset",
    ):
        assert not hasattr(suite, forbidden_member)
