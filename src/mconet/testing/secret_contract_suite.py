"""Reusable leak assertions for distinct observable secret carriers."""

from __future__ import annotations

from typing import cast

from mconet.testing.secret_scanner import SecretScanner


class SecretContractSuite:
    """Verify known test plaintext across four independent disclosure paths.

    The suite separates captured logs, raised exceptions, serialization output,
    and diagnostic snapshots so a contract failure identifies the observable
    boundary that leaked. Each operation delegates exact recursive matching to
    :class:`SecretScanner` and retains neither plaintext nor inspected values.

    Callers remain responsible for producing each carrier and for choosing the
    synthetic plaintext owned by the test. The suite performs no credential
    discovery, redaction, logging, exception normalization, serialization,
    snapshot construction, persistence, or fixture loading.
    """

    __slots__ = ()

    def assert_log_safe(self, secret: str, *entries: object) -> None:
        """Require known plaintext to be absent from captured log entries.

        Args:
            secret: Exact non-empty synthetic plaintext owned by the test.
            *entries: One or more captured log records or rendered log values.

        Raises:
            TypeError: If the secret, entry collection, or an entry is unsafe to
                inspect through the supported carrier boundary.
            AssertionError: If any captured log entry contains the plaintext.
        """
        # Keep log entries as separate top-level carriers so scanner locations
        # preserve their capture order without converting or joining records.
        SecretScanner().assert_absent(secret, *entries)

    def assert_exception_safe(self, secret: str, error: BaseException) -> None:
        """Require known plaintext to be absent from one raised exception.

        Args:
            secret: Exact non-empty synthetic plaintext owned by the test.
            error: Exact exception, including its chain and stored state.

        Raises:
            TypeError: If ``error`` is not an exception or contains data that
                cannot be inspected through the supported carrier boundary.
            AssertionError: If the exception contains the plaintext.
        """
        error_value = cast(object, error)
        # Reject ordinary objects before scanning so this category cannot be
        # used as an ambiguous general-carrier assertion by contract callers.
        if not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException.")
        SecretScanner().assert_absent(secret, error_value)

    def assert_serialization_safe(self, secret: str, serialized: object) -> None:
        """Require known plaintext to be absent from serialization output.

        Args:
            secret: Exact non-empty synthetic plaintext owned by the test.
            serialized: Complete text, bytes, or structured serialization result.

        Raises:
            TypeError: If the secret or output cannot be inspected through the
                supported carrier boundary.
            AssertionError: If the serialization output contains the plaintext.
        """
        # Inspect only the caller-produced result. Invoking serializers here
        # could introduce side effects and conflate production with assertion.
        SecretScanner().assert_absent(secret, serialized)

    def assert_snapshot_safe(self, secret: str, snapshot: object) -> None:
        """Require known plaintext to be absent from one diagnostic snapshot.

        Args:
            secret: Exact non-empty synthetic plaintext owned by the test.
            snapshot: Complete already-produced diagnostic snapshot value.

        Raises:
            TypeError: If the secret or snapshot cannot be inspected through the
                supported carrier boundary.
            AssertionError: If the diagnostic snapshot contains the plaintext.
        """
        # Snapshots may be nested data or SDK dataclasses. Delegate traversal to
        # the scanner without serializing, normalizing, or retaining the value.
        SecretScanner().assert_absent(secret, snapshot)
