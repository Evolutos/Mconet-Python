"""Field separation tests for monitoring options."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import MonitoringMergeMode, OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    InteractionMonitor,
    MonitoringEvent,
    MonitoringOptions,
)


class _Monitor:
    """Monitor fixture whose observation method must stay idle."""

    def __init__(self) -> None:
        """Store metadata and an invocation counter."""
        self.descriptor = ComponentDescriptor("monitor", "1.0.0", "application")
        self.observed_events = None
        self.calls: list[str] = []

    async def on_event(self, event: MonitoringEvent) -> None:
        """Record an event call that option construction must not make."""
        del event
        self.calls.append("on_event")


def test_defaults_keep_monitors_merge_mode_and_capture_separate() -> None:
    """Verify the empty options use append and leave capture off."""
    options = MonitoringOptions()
    assert options.monitors == ()
    assert str(options.merge_mode) == "append"
    assert options.capture_request_body is False
    assert options.capture_response_body is False
    assert options.max_captured_body_bytes is None


def test_each_field_can_change_without_the_others() -> None:
    """Verify monitors, merge mode, and capture flags are independent."""
    monitor = _Monitor()
    monitors = (cast(InteractionMonitor, monitor),)
    mode = MonitoringMergeMode(OpenIdentifier("prepend"))
    options = MonitoringOptions(
        monitors=monitors,
        merge_mode=mode,
        capture_request_body=True,
    )
    assert options.monitors is monitors
    assert options.merge_mode is mode
    assert options.capture_request_body is True
    assert options.capture_response_body is False
    assert options.max_captured_body_bytes is None
    assert monitor.calls == []

    captured = MonitoringOptions(capture_response_body=True, max_captured_body_bytes=0)
    assert captured.monitors == ()
    assert str(captured.merge_mode) == "append"
    assert captured.capture_request_body is False
    assert captured.capture_response_body is True
    assert captured.max_captured_body_bytes == 0


def test_open_merge_mode_is_preserved() -> None:
    """Keep a future merge mode instead of replacing it with append."""
    mode = MonitoringMergeMode(OpenIdentifier("future-mode"))
    options = MonitoringOptions(merge_mode=mode)
    assert options.merge_mode is mode
    assert options.monitors == ()


def test_monitor_collection_must_be_an_immutable_monitor_tuple() -> None:
    """Reject a mutable list and a value that is not a monitor."""
    try:
        MonitoringOptions(monitors=cast(tuple[InteractionMonitor, ...], []))
    except TypeError as error:
        assert "monitors must be a tuple" in str(error)
    else:
        raise AssertionError("Expected a list of monitors to be rejected.")

    try:
        MonitoringOptions(monitors=(cast(InteractionMonitor, object()),))
    except TypeError as error:
        assert "InteractionMonitor" in str(error)
    else:
        raise AssertionError("Expected a non-monitor to be rejected.")


def test_capture_fields_reject_non_booleans_and_a_negative_cap() -> None:
    """Reject numeric stand-ins for the capture switches and a negative cap."""
    try:
        MonitoringOptions(capture_request_body=cast(bool, 1))
    except TypeError as error:
        assert "capture_request_body must be a bool" in str(error)
    else:
        raise AssertionError("Expected a numeric capture flag to be rejected.")

    try:
        MonitoringOptions(max_captured_body_bytes=cast(int, True))
    except TypeError as error:
        assert "max_captured_body_bytes must be an int or None" in str(error)
    else:
        raise AssertionError("Expected a boolean cap to be rejected.")

    try:
        MonitoringOptions(max_captured_body_bytes=-1)
    except ValueError as error:
        assert "must not be negative" in str(error)
    else:
        raise AssertionError("Expected a negative cap to be rejected.")


def test_options_are_frozen() -> None:
    """Reject assignment after the separated fields are stored."""
    options = MonitoringOptions()
    try:
        options.capture_request_body = True  # type: ignore[misc]
    except FrozenInstanceError:
        assert options.capture_request_body is False
        return
    raise AssertionError("Expected frozen monitoring options.")
