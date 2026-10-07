"""Scenario coverage and concurrency tests for FaultInjectionHarness."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import cast

from mconet.core.domain import (
    Bytes,
    Duration,
    HeaderField,
    Headers,
    OpenIdentifier,
    Timestamp,
)
from mconet.core.spi import (
    TransportOutcome,
    TransportResponse,
    TransportResponseMetadata,
)
from mconet.testing import (
    ControllableCancellationSignal,
    FakeClock,
    FaultInjectionHarness,
)


def _response(
    status_code: int,
    body: bytes,
    *,
    content_type: str = "application/json",
) -> TransportResponse:
    """Build one scripted protocol-neutral response fault fixture."""
    # Outcome is derived by the test fixture explicitly; the harness does not
    # interpret native status codes or choose a decoder.
    outcome = "success" if 200 <= status_code < 300 else "failure"
    return TransportResponse(
        TransportResponseMetadata(
            TransportOutcome(OpenIdentifier(outcome)),
            Headers((HeaderField("Content-Type", content_type),)),
            status_code=status_code,
        ),
        Bytes(body),
    )


def _raising_action(failure: BaseException) -> Callable[[], object]:
    """Return one action that raises the exact supplied failure instance."""

    def raise_failure() -> object:
        """Raise the retained failure without wrapping or translation."""
        # BaseException includes cancellation and control-flow failures that a
        # deterministic fault scenario may intentionally exercise.
        raise failure

    return raise_failure


def test_harness_triggers_transport_and_payload_fault_categories() -> None:
    """Script timeout, cancellation, disconnect, response, and body failures."""
    clock = FakeClock(Timestamp(1_000, 0))
    signal = ControllableCancellationSignal()
    timeout_failure = TimeoutError("deadline exceeded")
    network_failure = OSError("connection reset")
    non_success_response = _response(503, b'{"error":"unavailable"}')
    invalid_json = Bytes(b'{"incomplete":')
    oversized_body = Bytes(b"x" * 4_097)
    wrong_content_type = _response(200, b'{"ok":true}', content_type="text/plain")

    def trigger_timeout() -> object:
        """Advance deterministic time before surfacing one timeout failure."""
        # Advancing first lets a test assert both deadline state and the exact
        # exception chosen for the timeout branch.
        clock.advance(Duration(5_000_000_000))
        raise timeout_failure

    harness = FaultInjectionHarness(
        {
            "transport.timeout": (trigger_timeout,),
            "transport.cancel": (lambda: signal.cancel("test_cancelled"),),
            "transport.disconnect": (_raising_action(network_failure),),
            "transport.non_success": (lambda: non_success_response,),
            "decoder.invalid_json": (lambda: invalid_json,),
            "transport.oversized_body": (lambda: oversized_body,),
            "decoder.wrong_content_type": (lambda: wrong_content_type,),
        }
    )

    try:
        harness.trigger("transport.timeout")
    except TimeoutError as error:
        assert error is timeout_failure
    else:
        raise AssertionError("Expected the timeout fault to be triggered.")
    assert clock.now() == Timestamp(1_005, 0)

    assert harness.trigger("transport.cancel") is None
    assert signal.is_cancelled
    assert signal.reason == "test_cancelled"

    try:
        harness.trigger("transport.disconnect")
    except OSError as error:
        assert error is network_failure
    else:
        raise AssertionError("Expected the network fault to be triggered.")

    assert harness.trigger("transport.non_success") is non_success_response
    assert non_success_response.response_metadata.status_code == 503
    assert harness.trigger("decoder.invalid_json") is invalid_json
    assert harness.trigger("transport.oversized_body") is oversized_body
    assert len(oversized_body) == 4_097
    assert harness.trigger("decoder.wrong_content_type") is wrong_content_type
    assert wrong_content_type.response_metadata.headers.get_all("content-type") == (
        "text/plain",
    )

    # Every category is reserved once in caller order, including raised actions.
    assert harness.calls == (
        "transport.timeout",
        "transport.cancel",
        "transport.disconnect",
        "transport.non_success",
        "decoder.invalid_json",
        "transport.oversized_body",
        "decoder.wrong_content_type",
    )


def test_harness_consumes_point_actions_in_fixed_order_and_preserves_identity() -> None:
    """Apply retry-specific outcomes once each without copying results."""
    first_failure = ConnectionError("first attempt failed")
    recovered = object()
    harness = FaultInjectionHarness(
        {
            "transport.send": (
                _raising_action(first_failure),
                lambda: recovered,
            )
        }
    )

    try:
        harness.trigger("transport.send")
    except ConnectionError as error:
        assert error is first_failure
    else:
        raise AssertionError("Expected the first scripted attempt to fail.")

    assert harness.trigger("transport.send") is recovered
    assert harness.calls == ("transport.send", "transport.send")

    try:
        harness.trigger("transport.send")
    except AssertionError as error:
        assert str(error) == "fault actions for the point are exhausted."
    else:
        raise AssertionError("Expected exhausted fault actions to fail.")
    # Harness misuse is not a reserved action and does not alter call evidence.
    assert harness.calls == ("transport.send", "transport.send")


def test_harness_snapshots_configuration_and_keeps_instances_isolated() -> None:
    """Prevent caller mutation and other harnesses from rewriting a scenario."""
    first_result = object()
    replacement = object()
    source_actions: list[Callable[[], object]] = [lambda: first_result]
    source: dict[str, Sequence[Callable[[], object]]] = {
        "adapter.prepare": source_actions
    }
    first = FaultInjectionHarness(source)
    second = FaultInjectionHarness({"adapter.prepare": (lambda: replacement,)})

    # Mutating both source levels after construction cannot replace the immutable
    # action sequence retained by the first harness.
    source_actions[0] = lambda: replacement
    source["adapter.prepare"] = (lambda: replacement,)

    assert first.trigger("adapter.prepare") is first_result
    assert second.trigger("adapter.prepare") is replacement
    assert first.calls == ("adapter.prepare",)
    assert second.calls == ("adapter.prepare",)


def test_harness_executes_actions_outside_lock_and_supports_reentrant_points() -> None:
    """Allow one action to trigger another checkpoint without deadlock."""
    inner_result = object()
    harness: FaultInjectionHarness

    def outer_action() -> object:
        """Trigger a second configured point while the first action executes."""
        # Reentrancy proves reservation synchronization does not wrap user code.
        return harness.trigger("monitor.failure")

    harness = FaultInjectionHarness(
        {
            "authorization.failure": (outer_action,),
            "monitor.failure": (lambda: inner_result,),
        }
    )

    assert harness.trigger("authorization.failure") is inner_result
    assert harness.calls == ("authorization.failure", "monitor.failure")


def test_harness_reserves_concurrent_actions_exactly_once() -> None:
    """Linearize concurrent triggers without duplicate or skipped actions."""
    action_count = 5_000
    actions = tuple((lambda result=result: result) for result in range(action_count))
    harness = FaultInjectionHarness({"transport.concurrent": actions})

    def trigger_concurrent(_: int) -> object:
        """Trigger one action using the executor's typed ordinal input."""
        return harness.trigger("transport.concurrent")

    with ThreadPoolExecutor(max_workers=32) as executor:
        results = tuple(
            executor.map(
                trigger_concurrent,
                range(action_count),
            )
        )

    # Thread completion order is scheduler-owned, but every queue position is
    # atomically consumed once and the complete result set remains deterministic.
    assert len(results) == action_count
    assert set(results) == set(range(action_count))
    assert harness.calls == ("transport.concurrent",) * action_count


def test_harness_rejects_unknown_points_and_invalid_trigger_labels() -> None:
    """Fail visibly when a test names no configured fault action."""
    harness = FaultInjectionHarness({"transport.send": (lambda: None,)})

    invalid_calls: tuple[tuple[Callable[[], object], type[BaseException], str], ...] = (
        (
            lambda: harness.trigger("decoder.decode"),
            AssertionError,
            "no fault actions are configured for the point",
        ),
        (
            lambda: harness.trigger(""),
            ValueError,
            "point must not be empty",
        ),
        (
            lambda: harness.trigger(cast(str, 1)),
            TypeError,
            "point must be a string",
        ),
    )

    for action, exception_type, message in invalid_calls:
        try:
            action()
        except exception_type as error:
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid trigger usage to fail.")
    assert harness.calls == ()


def test_harness_rejects_invalid_or_vacuous_configuration() -> None:
    """Detect malformed scenarios before any component operation begins."""

    async def asynchronous_action() -> object:
        """Represent an action the synchronous harness must reject."""
        return None

    invalid_configurations: tuple[
        tuple[
            object,
            type[BaseException],
            str,
        ],
        ...,
    ] = (
        ([], TypeError, "actions must be a mapping"),
        ({}, ValueError, "at least one fault point"),
        ({cast(str, 1): (lambda: None,)}, TypeError, "labels must be strings"),
        ({"": (lambda: None,)}, ValueError, "labels must not be empty"),
        (
            {"point": cast(Sequence[Callable[[], object]], object())},
            TypeError,
            "ordered sequence",
        ),
        ({"point": ()}, ValueError, "sequences must not be empty"),
        ({"point": (cast(Callable[[], object], 1),)}, TypeError, "must be callable"),
        (
            {"point": (asynchronous_action,)},
            TypeError,
            "actions must be synchronous",
        ),
    )

    for configuration, exception_type, message in invalid_configurations:
        try:
            FaultInjectionHarness(
                cast(Mapping[str, Sequence[Callable[[], object]]], configuration)
            )
        except exception_type as error:
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid fault configuration to fail.")


def test_harness_exposes_only_fixed_triggering_and_call_evidence() -> None:
    """Keep component behavior, clocks, cancellation, and retries outside scope."""
    harness = FaultInjectionHarness({"transport.send": (lambda: None,)})
    calls = inspect.getattr_static(FaultInjectionHarness, "calls")
    trigger = FaultInjectionHarness.trigger

    assert isinstance(calls, property)
    assert tuple(inspect.signature(FaultInjectionHarness).parameters) == ("actions",)
    assert tuple(inspect.signature(trigger).parameters) == ("self", "point")
    assert inspect.signature(trigger).return_annotation == "object"
    assert not inspect.iscoroutinefunction(trigger)
    assert not hasattr(harness, "__dict__")

    # The fixed harness cannot reconfigure component behavior or become the
    # owner of scheduling, time, cancellation, transport, decoding, or retries.
    for forbidden_member in (
        "configure",
        "register",
        "reset",
        "clear",
        "advance",
        "cancel",
        "send",
        "decode",
        "retry",
    ):
        assert not hasattr(harness, forbidden_member)
