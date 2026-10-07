"""Canonical structure and boundary tests for SnapshotComparator."""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable
from typing import cast

from mconet.core.domain import JsonValue
from mconet.testing import SnapshotComparator


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Checking stable wording ensures malformed snapshots are rejected by
        # canonical validation rather than treated as ordinary inequality.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_comparator_matches_nested_snapshots_independent_of_object_order() -> None:
    """Compare nested redacted objects without depending on insertion order."""
    comparator = SnapshotComparator()
    actual: JsonValue = {
        "request": {"token": "[REDACTED]", "attempt": 1},
        "events": [{"code": "sent", "ok": True}],
    }
    expected: JsonValue = {
        "events": [{"ok": True, "code": "sent"}],
        "request": {"attempt": 1.0, "token": "[REDACTED]"},
    }

    # Redaction markers are ordinary caller-owned JSON strings; comparison
    # applies structure rules without attempting to infer secret policy.
    assert comparator.compare(actual, expected)


def test_comparator_preserves_array_order_and_json_primitive_kinds() -> None:
    """Keep ordered events and prevent Python boolean-number coercion."""
    comparator = SnapshotComparator()

    assert not comparator.compare(["planned", "sent"], ["sent", "planned"])
    assert not comparator.compare(True, 1)
    assert not comparator.compare(None, "null")
    assert comparator.compare(-0.0, 0)


def test_comparator_detects_nested_shape_and_value_mismatches() -> None:
    """Include keys, container kinds, lengths, and scalar values in equality."""
    comparator = SnapshotComparator()

    assert not comparator.compare({"result": []}, {"result": {}})
    assert not comparator.compare({"result": [1]}, {"result": [1, 2]})
    assert not comparator.compare({"status": "ok"}, {"state": "ok"})
    assert not comparator.compare({"status": "ok"}, {"status": "failed"})


def test_comparator_rejects_non_json_and_non_portable_snapshot_values() -> None:
    """Reject malformed snapshot data instead of hiding it as a mismatch."""
    comparator = SnapshotComparator()

    _assert_raises(
        TypeError,
        lambda: comparator.compare(cast(JsonValue, {"value": b"secret"}), {}),
        "structurally valid JsonValue",
    )
    for value in (2**53, math.nan, math.inf):
        _assert_raises(
            ValueError,
            lambda value=value: comparator.compare(cast(JsonValue, value), 0),
            "JSON",
        )


def test_comparator_does_not_mutate_or_retain_snapshots() -> None:
    """Leave inputs intact and retain no sensitive comparison state."""
    comparator = SnapshotComparator()
    actual: JsonValue = {"headers": {"authorization": "[REDACTED]"}}
    expected: JsonValue = {"headers": {"authorization": "[REDACTED]"}}
    actual_before = repr(actual)
    expected_before = repr(expected)

    assert comparator.compare(actual, expected)

    # Exact representations confirm key order and values were not normalized
    # in place, while the slot-only stateless instance cannot retain inputs.
    assert repr(actual) == actual_before
    assert repr(expected) == expected_before
    assert not hasattr(comparator, "__dict__")


def test_comparator_handles_deep_snapshots_without_recursion() -> None:
    """Compare valid snapshot depth independently of Python's call stack."""
    actual: JsonValue = "[REDACTED]"
    expected: JsonValue = "[REDACTED]"
    for _ in range(2_000):
        # Separate arrays ensure equality traverses the complete structure and
        # cannot succeed from shared container identity.
        actual = [actual]
        expected = [expected]

    assert SnapshotComparator().compare(actual, expected)


def test_comparator_exposes_only_one_synchronous_comparison_operation() -> None:
    """Keep redaction, persistence, updates, and diagnostics outside the type."""
    comparator = SnapshotComparator()
    compare = SnapshotComparator.compare
    signature = inspect.signature(compare)

    assert tuple(signature.parameters) == (
        "self",
        "actual",
        "expected",
    )
    assert signature.parameters["actual"].annotation == "JsonValue"
    assert signature.parameters["expected"].annotation == "JsonValue"
    assert signature.return_annotation == "bool"
    assert not inspect.iscoroutinefunction(compare)

    # Snapshot lifecycle and security policy remain explicit responsibilities
    # of fixtures and callers rather than hidden comparator side effects.
    for forbidden_member in (
        "redact",
        "serialize",
        "diff",
        "update",
        "save",
        "load",
        "reset",
        "history",
    ):
        assert not hasattr(comparator, forbidden_member)
