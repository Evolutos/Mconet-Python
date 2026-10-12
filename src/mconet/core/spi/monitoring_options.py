"""Immutable monitoring configuration separate from component injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.monitoring_merge_mode import MonitoringMergeMode
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.spi.interaction_monitor import InteractionMonitor

_APPEND = MonitoringMergeMode(OpenIdentifier("append"))


@dataclass(frozen=True, slots=True)
class MonitoringOptions:
    """Store monitors, their merge mode, and body-capture switches separately.

    The monitor tuple is the ordered observer list. ``merge_mode`` names how a
    later interaction list combines with a client list; this value does not
    merge them. The capture flags and optional byte cap describe whether a
    later monitoring stage may retain request or response body bytes. They do
    not capture, redact, or copy a body.

    Defaults observe nothing: an empty monitor tuple, ``append``, both capture
    flags false, and no byte cap. An open merge-mode identifier is preserved
    rather than rewritten to ``append``.
    """

    monitors: tuple[InteractionMonitor, ...] = ()
    """Ordered monitors contributed by this configuration layer."""

    merge_mode: MonitoringMergeMode = _APPEND
    """Strategy for combining this monitor list with another layer."""

    capture_request_body: bool = False
    """Whether a later stage may retain redacted request body bytes."""

    capture_response_body: bool = False
    """Whether a later stage may retain redacted response body bytes."""

    max_captured_body_bytes: int | None = None
    """Optional non-negative cap for one retained body, or no explicit cap."""

    def __post_init__(self) -> None:
        """Require separated, immutable monitoring fields."""
        monitors = cast(object, self.monitors)
        merge_mode = cast(object, self.merge_mode)
        capture_request_body = cast(object, self.capture_request_body)
        capture_response_body = cast(object, self.capture_response_body)
        max_captured_body_bytes = cast(object, self.max_captured_body_bytes)

        # A list would let a caller change the observer order after the client
        # stored the options. Membership is checked without calling monitors.
        if not isinstance(monitors, tuple):
            raise TypeError("monitors must be a tuple.")
        for monitor in cast(tuple[object, ...], monitors):
            if not isinstance(monitor, InteractionMonitor):
                raise TypeError("monitors must contain InteractionMonitor values.")
        if not isinstance(merge_mode, MonitoringMergeMode):
            raise TypeError("merge_mode must be a MonitoringMergeMode.")
        # bool is required exactly so 0 and 1 cannot silently change a capture
        # switch while leaving the monitor list and merge mode untouched.
        if type(capture_request_body) is not bool:
            raise TypeError("capture_request_body must be a bool.")
        if type(capture_response_body) is not bool:
            raise TypeError("capture_response_body must be a bool.")
        if (
            max_captured_body_bytes is not None
            and type(max_captured_body_bytes) is not int
        ):
            raise TypeError("max_captured_body_bytes must be an int or None.")
        if isinstance(max_captured_body_bytes, int) and max_captured_body_bytes < 0:
            raise ValueError("max_captured_body_bytes must not be negative.")
