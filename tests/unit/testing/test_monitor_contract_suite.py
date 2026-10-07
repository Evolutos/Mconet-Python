"""Filter, privacy, read-only, and failure-isolation tests for MonitorContractSuite."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import JsonValue, OpenIdentifier, Timestamp
from mconet.core.spi import (
    ComponentDescriptor,
    InteractionMonitor,
    MonitoringEvent,
)
from mconet.testing import MonitorContractSuite, StubInteractionMonitor

_KNOWN_PLAINTEXT = "-".join(("monitor", "private", "marker"))


class _RecordingMonitor:
    """Structural monitor recording exact events and one configured outcome."""

    __slots__ = ("_descriptor", "_error", "_events", "_observed_events", "_result")

    def __init__(
        self,
        observed_events: frozenset[OpenIdentifier] | None,
        *,
        result: object = None,
        error: BaseException | None = None,
    ) -> None:
        """Retain filter and outcome while initializing an empty event record."""
        self._descriptor = ComponentDescriptor("Recording monitor", "1", "application")
        self._observed_events = observed_events
        self._result = result
        self._error = error
        self._events: list[MonitoringEvent] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable monitor metadata."""
        # Return the exact constructor-owned value so Suite initialization cannot
        # observe generated or replaceable component metadata.
        return self._descriptor

    @property
    def observed_events(self) -> frozenset[OpenIdentifier] | None:
        """Return the configured immutable event filter."""
        # Exact optional-state and membership are stable until a specialized
        # hostile fixture deliberately changes them.
        return self._observed_events

    @property
    def events(self) -> tuple[MonitoringEvent, ...]:
        """Return an immutable snapshot of received event identities."""
        # A tuple protects recorded membership while retaining the exact event
        # references supplied through each async observation.
        return tuple(self._events)

    async def on_event(self, event: MonitoringEvent) -> None:
        """Record one event, then return or raise the configured outcome."""
        # Yield once to exercise a genuine asynchronous boundary before making
        # invocation and outcome behavior observable.
        await asyncio.sleep(0)
        self._events.append(event)
        if self._error is not None:
            raise self._error
        return cast(None, self._result)


class _MutatingMonitor:
    """Monitor intentionally changing nested event payload before its outcome."""

    __slots__ = ("_error",)

    descriptor = ComponentDescriptor("Mutating monitor", "1", "application")
    """Valid metadata isolates event read-only enforcement."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """Stable all-events filter keeps mutation as the only violation."""

    def __init__(self, *, error: BaseException | None = None) -> None:
        """Retain an optional failure raised after payload mutation."""
        self._error = error

    async def on_event(self, event: MonitoringEvent) -> None:
        """Mutate nested payload data, then return or raise."""
        # MonitoringEvent freezes top-level assignment but intentionally retains
        # JSON containers; this hostile fixture proves deep mutation is detected.
        payload = cast(dict[str, JsonValue], event.payload)
        nested = cast(dict[str, JsonValue], payload["nested"])
        nested["state"] = "changed"
        if self._error is not None:
            raise self._error


class _ChangingFilterMonitor:
    """Monitor changing its subscription after observing an event."""

    __slots__ = ("_observed_events",)

    descriptor = ComponentDescriptor("Changing filter", "1", "application")
    """Valid metadata isolates subscription stability."""

    def __init__(self) -> None:
        """Initialize one selected-event subscription."""
        self._observed_events = frozenset((OpenIdentifier("interaction.started"),))

    @property
    def observed_events(self) -> frozenset[OpenIdentifier] | None:
        """Return the current subscription membership."""
        # The property is structurally valid even though on_event later violates
        # the protocol's fixed-membership requirement.
        return self._observed_events

    async def on_event(self, event: MonitoringEvent) -> None:
        """Replace filter membership after accepting the event."""
        del event
        self._observed_events = frozenset((OpenIdentifier("interaction.failed"),))


class _BlockingMonitor:
    """Monitor remaining pending until its surrounding task is cancelled."""

    __slots__ = ("started",)

    descriptor = ComponentDescriptor("Blocking monitor", "1", "application")
    """Valid metadata isolates external task cancellation."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """Stable all-events filter avoids subscription side effects."""

    def __init__(self) -> None:
        """Create one event signalling that observation began."""
        self.started = asyncio.Event()

    async def on_event(self, event: MonitoringEvent) -> None:
        """Signal entry and remain pending without producing a monitor failure."""
        del event
        self.started.set()
        # A fresh unset event never completes normally; cancellation of the
        # surrounding assertion task must propagate through this await.
        await asyncio.Event().wait()


class _IncompleteMonitor:
    """Component-shaped fixture intentionally missing event observation."""

    descriptor = ComponentDescriptor("Incomplete monitor", "1", "application")
    """Valid metadata isolates absence of on_event."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """Valid filtering cannot replace required observation behavior."""


class _InvalidDescriptorMonitor:
    """Complete monitor surface exposing malformed component metadata."""

    descriptor = cast(ComponentDescriptor, object())
    """Invalid metadata used only for constructor rejection."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """Valid all-events filter keeps descriptor failure isolated."""

    async def on_event(self, event: MonitoringEvent) -> None:
        """Discard an event if called unexpectedly."""
        # Constructor validation must fail before this callback can execute.
        del event


class _SyncMonitor:
    """Expose an invalid synchronous event observation operation."""

    descriptor = ComponentDescriptor("Sync monitor", "1", "application")
    """Valid metadata isolates async-boundary enforcement."""

    observed_events: frozenset[OpenIdentifier] | None = None
    """Valid filter keeps callback shape as the only violation."""

    def on_event(self, event: MonitoringEvent) -> None:
        """Discard the event synchronously if called unexpectedly."""
        # Suite construction must reject this method before invocation.
        del event


class _InvalidFilterMonitor:
    """Complete async monitor exposing a malformed filter value."""

    descriptor = ComponentDescriptor("Invalid filter", "1", "application")
    """Valid metadata keeps filter validation isolated."""

    observed_events = cast(frozenset[OpenIdentifier] | None, set())
    """Mutable membership violates the public immutable filter type."""

    async def on_event(self, event: MonitoringEvent) -> None:
        """Discard an event if called unexpectedly."""
        del event


def _event(
    *,
    payload: JsonValue | None = None,
    metadata: dict[str, JsonValue] | None = None,
) -> MonitoringEvent:
    """Build one complete privacy-bounded immutable lifecycle event."""
    # Defaults contain nested non-sensitive JSON so successful observations also
    # exercise full structural read-only comparison.
    actual_payload: JsonValue = (
        {"state": "observed", "nested": {"state": "original"}}
        if payload is None
        else payload
    )
    actual_metadata = {"region": "test-region"} if metadata is None else metadata
    return MonitoringEvent(
        id="event-1",
        type=OpenIdentifier("integration.resolved"),
        interaction_id="interaction-1",
        trace_id="trace-1",
        timestamp=Timestamp(1_800_000_000, 123_456_789),
        payload=actual_payload,
        metadata=actual_metadata,
    )


def _stub(
    observed_events: frozenset[OpenIdentifier] | None = None,
    *,
    error: BaseException | None = None,
) -> StubInteractionMonitor:
    """Build one existing monitor Stub with deterministic configuration."""
    # Centralized metadata keeps contract tests focused on subscription,
    # observation, privacy, read-only behavior, or failure isolation.
    return StubInteractionMonitor(
        ComponentDescriptor("Stub monitor", "1", "application"),
        observed_events,
        error=error,
    )


def _assert_nothing(value: object) -> None:
    """Accept a callback value when the case targets another boundary."""
    # Explicit disposal documents that callback behavior must not influence the
    # contract failure being exercised.
    del value


def _assert_type_error(action: Callable[[], object], message: str) -> None:
    """Require monitor Suite construction to fail with one exact diagnostic."""
    try:
        action()
    except TypeError as error:
        assert str(error) == message
        return
    raise AssertionError("Expected contract setup to reject an invalid type.")


def _construct_incomplete_suite() -> object:
    """Attempt construction with a monitor missing on_event."""
    # The cast deliberately crosses static checking so runtime structural
    # recognition must reject the incomplete monitor.
    return MonitorContractSuite(cast(InteractionMonitor, _IncompleteMonitor()))


def _construct_invalid_descriptor_suite() -> object:
    """Attempt construction with malformed monitor metadata."""
    # Complete async behavior isolates nominal descriptor validation.
    return MonitorContractSuite(_InvalidDescriptorMonitor())


def _construct_sync_suite() -> object:
    """Attempt construction with synchronous observation behavior."""
    # Runtime protocol recognition accepts the member name; Suite construction
    # must additionally enforce asynchronous execution.
    return MonitorContractSuite(cast(InteractionMonitor, _SyncMonitor()))


def _construct_invalid_filter_suite() -> object:
    """Attempt construction with mutable filter membership."""
    # Async behavior and metadata are valid, leaving only filter shape invalid.
    return MonitorContractSuite(_InvalidFilterMonitor())


def test_suite_exposes_all_events_and_selected_event_filters() -> None:
    """Preserve None and immutable selected-event subscription semantics."""
    selected = frozenset(
        (OpenIdentifier("integration.resolved"), OpenIdentifier("interaction.failed"))
    )
    all_suite = MonitorContractSuite(_stub())
    selected_suite = MonitorContractSuite(_stub(selected))
    observed: list[frozenset[OpenIdentifier] | None] = []

    def assert_all_events(actual: frozenset[OpenIdentifier] | None) -> None:
        """Require the explicit all-events declaration."""
        assert actual is None
        observed.append(actual)

    def assert_selected(actual: frozenset[OpenIdentifier] | None) -> None:
        """Require exact selected membership and immutable storage."""
        assert actual is selected
        assert not hasattr(actual, "add")
        observed.append(actual)

    all_suite.assert_observed_events(assertion=assert_all_events)
    selected_suite.assert_observed_events(assertion=assert_selected)

    assert observed == [None, selected]


def test_suite_observes_exact_safe_event_with_existing_stub() -> None:
    """Deliver one redacted event by identity and require a None result."""
    event = _event()
    stub = _stub()
    observed: list[MonitoringEvent] = []

    def assert_event(actual: MonitoringEvent) -> None:
        """Require exact event identity and unchanged nested data."""
        assert actual is event
        payload = cast(dict[str, JsonValue], actual.payload)
        assert payload["nested"] == {"state": "original"}
        observed.append(actual)

    asyncio.run(
        MonitorContractSuite(stub).assert_observe(
            event,
            secret=_KNOWN_PLAINTEXT,
            assertion=assert_event,
        )
    )

    assert stub.events == (event,)
    assert stub.events[0] is event
    assert observed == [event]


def test_suite_rejects_known_plaintext_before_monitor_invocation() -> None:
    """Prevent a leaking event from reaching any monitor callback."""
    event = _event(payload={"credential": _KNOWN_PLAINTEXT})
    stub = _stub()

    try:
        asyncio.run(
            MonitorContractSuite(stub).assert_observe(
                event,
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
    except AssertionError as error:
        # Scanner diagnostics contain only structural locations and never repeat
        # the protected plaintext rejected by the privacy boundary.
        assert "Secret detected in an inspected carrier." in str(error)
        assert _KNOWN_PLAINTEXT not in str(error)
    else:
        raise AssertionError("Expected a plaintext monitoring leak to fail.")

    assert stub.events == ()


def test_suite_rejects_event_mutation_on_success_and_failure() -> None:
    """Detect nested payload mutation before result or failure assertions."""
    success_event = _event()
    try:
        asyncio.run(
            MonitorContractSuite(_MutatingMonitor()).assert_observe(
                success_event,
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
    except AssertionError as error:
        assert str(error) == "monitor must not mutate the monitoring event."
    else:
        raise AssertionError("Expected successful event mutation to fail.")

    monitor_failure = RuntimeError("export failed after mutation")
    callback_called = False

    def assert_failure(actual: BaseException) -> None:
        """Record an unexpected callback after event mutation."""
        nonlocal callback_called
        del actual
        callback_called = True

    try:
        asyncio.run(
            MonitorContractSuite(
                _MutatingMonitor(error=monitor_failure)
            ).assert_failure_isolated(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=assert_failure,
            )
        )
    except AssertionError as error:
        assert str(error) == "monitor must not mutate the monitoring event."
        assert error is not monitor_failure
    else:
        raise AssertionError("Expected failing event mutation to fail closed.")

    assert not callback_called


def test_suite_detects_event_filter_changes_after_observation() -> None:
    """Require selected-event membership to remain fixed during interaction."""
    suite = MonitorContractSuite(_ChangingFilterMonitor())

    try:
        asyncio.run(
            suite.assert_observe(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
    except AssertionError as error:
        assert str(error) == "monitor observed_events must remain unchanged."
    else:
        raise AssertionError("Expected filter replacement to fail.")


def test_suite_isolates_exact_monitor_failure_with_existing_stub() -> None:
    """Consume one diagnostic failure while exposing it exactly to assertion."""
    failure = RuntimeError("monitor exporter unavailable")
    event = _event()
    stub = _stub(error=failure)
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require exact isolated failure identity and event recording."""
        assert actual is failure
        assert stub.events == (event,)
        observed.append(actual)

    # Normal completion proves the monitor failure was isolated rather than
    # propagated as the surrounding interaction outcome.
    result = asyncio.run(
        MonitorContractSuite(stub).assert_failure_isolated(
            event,
            secret=_KNOWN_PLAINTEXT,
            assertion=assert_failure,
        )
    )

    assert result is None
    assert observed == [failure]


def test_suite_propagates_external_task_cancellation() -> None:
    """Keep caller-owned cancellation separate from monitor-only failures."""

    async def run_case() -> None:
        """Cancel one active failure-isolation assertion after monitor entry."""
        monitor = _BlockingMonitor()
        task = asyncio.create_task(
            MonitorContractSuite(monitor).assert_failure_isolated(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
        await monitor.started.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            # Propagation proves failure isolation did not consume interaction
            # control requested on the current assertion task.
            return
        raise AssertionError("Expected external task cancellation to propagate.")

    asyncio.run(run_case())


def test_suite_rejects_non_none_result_and_unexpected_success() -> None:
    """Keep monitor callbacks control-free in success and failure cases."""
    returning = _RecordingMonitor(None, result="stop-interaction")
    try:
        asyncio.run(
            MonitorContractSuite(returning).assert_observe(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
    except AssertionError as error:
        assert str(error) == "monitor on_event must return None."
    else:
        raise AssertionError("Expected a control-like monitor result to fail.")

    successful = _stub()
    try:
        asyncio.run(
            MonitorContractSuite(successful).assert_failure_isolated(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
    except AssertionError as error:
        assert str(error) == "monitor was expected to fail observation."
    else:
        raise AssertionError("Expected failure-case success to be rejected.")


def test_suite_preserves_success_and_failure_assertion_exceptions() -> None:
    """Propagate exact assertion errors outside monitor control flow."""
    success_assertion_error = RuntimeError("success assertion failed")
    monitor_failure = RuntimeError("monitor failed")
    failure_assertion_error = RuntimeError("failure assertion failed")

    def fail_success_assertion(actual: MonitoringEvent) -> None:
        """Raise one exact callback error after successful observation."""
        del actual
        raise success_assertion_error

    def fail_failure_assertion(actual: BaseException) -> None:
        """Confirm monitor failure, then raise one exact callback error."""
        assert actual is monitor_failure
        raise failure_assertion_error

    try:
        asyncio.run(
            MonitorContractSuite(_stub()).assert_observe(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=fail_success_assertion,
            )
        )
    except RuntimeError as error:
        assert error is success_assertion_error
    else:
        raise AssertionError("Expected success assertion to fail.")

    try:
        asyncio.run(
            MonitorContractSuite(_stub(error=monitor_failure)).assert_failure_isolated(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=fail_failure_assertion,
            )
        )
    except RuntimeError as error:
        assert error is failure_assertion_error
        assert error is not monitor_failure
    else:
        raise AssertionError("Expected failure assertion to fail.")


def test_suite_snapshots_deep_event_json_without_python_recursion() -> None:
    """Keep valid event depth independent from recursive comparison limits."""
    deep_value: JsonValue = "leaf"
    for _ in range(2_000):
        # Separate arrays form a valid deep JSON graph that recursive copy or
        # equality implementations cannot safely process.
        deep_value = [deep_value]
    event = _event(payload={"deep": deep_value})
    stub = _stub()

    def assert_event(actual: MonitoringEvent) -> None:
        """Require exact identity after deep pre/post snapshots."""
        assert actual is event

    asyncio.run(
        MonitorContractSuite(stub).assert_observe(
            event,
            secret=_KNOWN_PLAINTEXT,
            assertion=assert_event,
        )
    )

    assert cast(dict[str, JsonValue], event.payload)["deep"] is deep_value


def test_suite_rejects_invalid_monitor_shapes_at_construction() -> None:
    """Reject incomplete, malformed, synchronous, and mutable-filter monitors."""
    _assert_type_error(
        _construct_incomplete_suite,
        "monitor must implement InteractionMonitor.",
    )
    _assert_type_error(
        _construct_invalid_descriptor_suite,
        "monitor descriptor must be a ComponentDescriptor.",
    )
    _assert_type_error(
        _construct_sync_suite,
        "monitor on_event operation must be asynchronous.",
    )
    _assert_type_error(
        _construct_invalid_filter_suite,
        "monitor observed_events must be a frozenset or None.",
    )


def test_suite_validates_event_secret_and_assertion_before_observation() -> None:
    """Reject malformed test setup before invoking the monitor callback."""
    monitor = _RecordingMonitor(None)
    suite = MonitorContractSuite(monitor)

    try:
        asyncio.run(
            suite.assert_observe(
                cast(MonitoringEvent, object()),
                secret=_KNOWN_PLAINTEXT,
                assertion=_assert_nothing,
            )
        )
    except TypeError as error:
        assert str(error) == "event must be a MonitoringEvent."
    else:
        raise AssertionError("Expected an invalid event to fail.")

    try:
        asyncio.run(
            suite.assert_observe(
                _event(),
                secret="",
                assertion=_assert_nothing,
            )
        )
    except TypeError as error:
        assert str(error) == "secret must be a non-empty string."
    else:
        raise AssertionError("Expected an empty secret marker to fail.")

    try:
        asyncio.run(
            suite.assert_observe(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=cast(Callable[[MonitoringEvent], None], object()),
            )
        )
    except TypeError as error:
        assert str(error) == "assertion must be callable."
    else:
        raise AssertionError("Expected a non-callable assertion to fail.")

    assert monitor.events == ()


def test_suite_rejects_async_assertion_before_observation() -> None:
    """Prevent an unawaited assertion callback from crossing the async API."""
    monitor = _RecordingMonitor(None)

    async def assert_event(actual: MonitoringEvent) -> None:
        """Represent one invalid asynchronous assertion callback."""
        # The Suite must reject this function before monitor observation.
        del actual

    try:
        asyncio.run(
            MonitorContractSuite(monitor).assert_observe(
                _event(),
                secret=_KNOWN_PLAINTEXT,
                assertion=cast(Callable[[MonitoringEvent], None], assert_event),
            )
        )
    except TypeError as error:
        assert str(error) == "assertion must be synchronous."
    else:
        raise AssertionError("Expected an async assertion to be rejected.")

    assert monitor.events == ()


def test_suite_exposes_exact_filter_and_observation_surface() -> None:
    """Keep filtering decisions, export, interception, and execution out of scope."""
    suite = MonitorContractSuite(_stub())
    filter_method = MonitorContractSuite.assert_observed_events
    observe_method = MonitorContractSuite.assert_observe
    failure_method = MonitorContractSuite.assert_failure_isolated

    # The filter assertion is synchronous and receives no event; observation
    # methods are async and share the exact event/privacy/callback shape.
    assert tuple(inspect.signature(filter_method).parameters) == (
        "self",
        "assertion",
    )
    assert get_type_hints(filter_method) == {
        "assertion": Callable[[frozenset[OpenIdentifier] | None], None],
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(filter_method)

    for operation, callback_type in (
        (observe_method, Callable[[MonitoringEvent], None]),
        (failure_method, Callable[[BaseException], None]),
    ):
        assert tuple(inspect.signature(operation).parameters) == (
            "self",
            "event",
            "secret",
            "assertion",
        )
        assert get_type_hints(operation) == {
            "event": MonitoringEvent,
            "secret": str,
            "assertion": callback_type,
            "return": type(None),
        }
        assert inspect.iscoroutinefunction(operation)

    for forbidden_member in (
        "filter",
        "publish",
        "export",
        "request",
        "next",
        "stop",
        "cancel",
        "modify_request",
        "encode",
        "authorize",
        "send",
        "retry",
        "reset",
    ):
        assert not hasattr(suite, forbidden_member)
