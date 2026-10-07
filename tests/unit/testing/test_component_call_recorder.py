"""Ordering, snapshot, and concurrency tests for ComponentCallRecorder."""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import cast, get_type_hints

from mconet.testing import ComponentCallRecorder


def test_recorder_starts_empty_and_records_complete_pipeline_order() -> None:
    """Preserve the exact plan-through-parse sequence for one interaction."""
    recorder = ComponentCallRecorder()

    for call in ("plan", "encode", "authorize", "send", "decode", "parse"):
        recorder.record(call)

    # Direct tuple equality supplies the intended assertion surface without a
    # recorder-owned test framework, partial-order matcher, or hidden stages.
    assert recorder.calls == (
        "plan",
        "encode",
        "authorize",
        "send",
        "decode",
        "parse",
    )


def test_recorder_preserves_open_duplicate_and_empty_labels_exactly() -> None:
    """Retain caller data without imposing one closed component vocabulary."""
    recorder = ComponentCallRecorder()
    labels = ("encode", "encode", "provider.Custom", "", " parse ")

    for label in labels:
        recorder.record(label)

    # Duplicate calls remain independently visible, while extension spelling,
    # casing, empty markers, and surrounding whitespace are never normalized.
    assert recorder.calls == labels


def test_recorder_snapshots_are_immutable_and_time_bounded() -> None:
    """Prevent callers and later records from changing an earlier observation."""
    recorder = ComponentCallRecorder()
    recorder.record("plan")
    first_snapshot = recorder.calls

    recorder.record("encode")
    second_snapshot = recorder.calls

    # Each read builds a fresh immutable view; later append changes only the
    # internal history and future snapshots.
    assert first_snapshot == ("plan",)
    assert second_snapshot == ("plan", "encode")
    assert first_snapshot is not second_snapshot
    assert not hasattr(first_snapshot, "append")


def test_recorder_keeps_instance_histories_isolated() -> None:
    """Avoid shared call evidence and test-order dependence."""
    first = ComponentCallRecorder()
    second = ComponentCallRecorder()

    first.record("plan")
    second.record("decode")
    first.record("encode")

    # Each interaction or test gets an independent sequence with no global log.
    assert first.calls == ("plan", "encode")
    assert second.calls == ("decode",)


def test_recorder_retains_every_concurrent_call_once() -> None:
    """Linearize concurrent appends without loss or duplication."""
    recorder = ComponentCallRecorder()
    labels = tuple(f"call-{index}" for index in range(5_000))

    with ThreadPoolExecutor(max_workers=32) as executor:
        results = tuple(executor.map(recorder.record, labels))

    # Worker completion order is scheduler-owned, but the recorded sequence is a
    # complete linearization containing each exact caller label once.
    assert results == (None,) * len(labels)
    assert len(recorder.calls) == len(labels)
    assert len(set(recorder.calls)) == len(labels)
    assert set(recorder.calls) == set(labels)

    recorder.record("after-concurrency")
    assert recorder.calls[-1] == "after-concurrency"


def test_recorder_rejects_non_string_call_without_mutating_history() -> None:
    """Fail malformed dynamic use before it can corrupt ordering evidence."""
    recorder = ComponentCallRecorder()
    recorder.record("plan")

    try:
        recorder.record(cast(str, object()))
    except TypeError as error:
        # Stable wording distinguishes recorder misuse from a component failure.
        assert "call must be a string" in str(error)
    else:
        raise AssertionError("Expected invalid call label to fail.")

    assert recorder.calls == ("plan",)


def test_recorder_has_exact_minimal_surface() -> None:
    """Expose only immutable history reads and synchronous label recording."""
    recorder = ComponentCallRecorder()
    calls = inspect.getattr_static(ComponentCallRecorder, "calls")
    record = ComponentCallRecorder.record

    # The public API contains one read-only property and one immediate operation.
    assert isinstance(calls, property)
    assert calls.fget is not None
    assert get_type_hints(calls.fget) == {"return": tuple[str, ...]}
    assert tuple(inspect.signature(record).parameters) == ("self", "call")
    assert get_type_hints(record) == {
        "call": str,
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(record)
    assert not hasattr(recorder, "__dict__")

    # Arguments, outcomes, time, assertions, wrappers, filtering, and lifecycle
    # rewrites remain the responsibility of tests and component-specific doubles.
    for forbidden_member in (
        "reset",
        "clear",
        "assert_calls",
        "arguments",
        "results",
        "errors",
        "timestamps",
        "wrap",
        "filter",
    ):
        assert not hasattr(recorder, forbidden_member)
