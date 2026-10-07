"""Deterministic checkpoint actions for fault-injection tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from inspect import iscoroutinefunction
from threading import Lock
from typing import cast


class FaultInjectionHarness:
    """Trigger fixed one-use actions at caller-owned fault checkpoints.

    Construction snapshots an ordered action sequence for every non-empty point
    label. Each :meth:`trigger` call atomically reserves the next action for its
    point, records the invocation, and then executes that action outside the
    synchronization lock. Returned objects and raised exceptions pass through
    unchanged.

    Actions can therefore return scripted response metadata or body bytes, raise
    transport and decoding failures, advance a fake clock, or cancel a controlled
    signal. This mechanism defines timing and consumption only; component Stubs,
    MockTransport, clocks, cancellation signals, and future local servers remain
    the owners of their protocol-specific behavior.

    Configuration is immutable after construction. Exhausted and unknown points
    fail instead of silently becoming successful no-ops, so a test cannot pass
    after accidentally consuming its intended fault too early. Action execution
    occurs without the lock, permitting reentrant triggers and avoiding hidden
    serialization of test behavior.
    """

    __slots__ = ("_actions", "_calls", "_lock", "_next_indexes")

    def __init__(
        self,
        actions: Mapping[str, Sequence[Callable[[], object]]],
    ) -> None:
        """Validate and snapshot ordered fault actions for every point.

        Args:
            actions: Non-empty mapping from exact point labels to non-empty
                ordered sequences of zero-argument actions.

        Raises:
            TypeError: If the mapping, a point, a sequence, or an action has an
                invalid runtime type.
            ValueError: If the mapping, a point, or an action sequence is empty.
        """
        actions_value = cast(object, actions)
        if not isinstance(actions_value, Mapping):
            raise TypeError("actions must be a mapping.")

        # Materialize caller configuration before publishing any instance state,
        # preventing later mapping or sequence mutation from rewriting a scenario.
        configured: dict[str, tuple[Callable[[], object], ...]] = {}
        for point, point_actions in cast(
            Mapping[object, object], actions_value
        ).items():
            if type(point) is not str:
                raise TypeError("fault point labels must be strings.")
            if not point:
                raise ValueError("fault point labels must not be empty.")
            if not isinstance(point_actions, Sequence) or isinstance(
                point_actions, (str, bytes, bytearray)
            ):
                raise TypeError("fault actions must be an ordered sequence.")

            action_snapshot = tuple(cast(Sequence[object], point_actions))
            if not action_snapshot:
                raise ValueError("fault action sequences must not be empty.")
            for action in action_snapshot:
                if not callable(action):
                    raise TypeError("every fault action must be callable.")
                if iscoroutinefunction(action) or iscoroutinefunction(
                    type(action).__call__
                ):
                    # Calling an async function would only manufacture a dormant
                    # coroutine. Scheduling and awaiting belong to the test/server.
                    raise TypeError("fault actions must be synchronous.")
            configured[point] = cast(
                tuple[Callable[[], object], ...],
                action_snapshot,
            )

        if not configured:
            raise ValueError("at least one fault point must be configured.")

        # All mutable scenario state is instance-local and guarded by one lock.
        # Index dictionaries avoid removing actions or mutating immutable tuples.
        self._lock = Lock()
        self._actions = configured
        self._next_indexes = dict.fromkeys(configured, 0)
        self._calls: list[str] = []

    @property
    def calls(self) -> tuple[str, ...]:
        """Return an immutable snapshot of successfully reserved point labels."""
        with self._lock:
            # Copy under the reservation lock so the snapshot corresponds to one
            # complete prefix even while other threads trigger later actions.
            return tuple(self._calls)

    def trigger(self, point: str) -> object:
        """Reserve and execute the next action for one fault point.

        Args:
            point: Exact caller-owned checkpoint label selected for this trigger.

        Returns:
            The exact object returned by the reserved action, including ``None``.

        Raises:
            TypeError: If ``point`` is not an exact string.
            ValueError: If ``point`` is empty.
            AssertionError: If the point is unknown or its actions are exhausted.
            BaseException: The exact failure raised by the reserved action.
        """
        point_value = cast(object, point)
        if type(point_value) is not str:
            raise TypeError("point must be a string.")
        if not point:
            raise ValueError("point must not be empty.")

        with self._lock:
            point_actions = self._actions.get(point)
            if point_actions is None:
                # Fixed wording intentionally omits caller data so a malformed
                # point cannot unexpectedly enter test logs through this error.
                raise AssertionError("no fault actions are configured for the point.")
            next_index = self._next_indexes[point]
            if next_index >= len(point_actions):
                raise AssertionError("fault actions for the point are exhausted.")

            # Reservation is the concurrency linearization point. Record before
            # execution so a raised action remains visible as a triggered fault.
            action = point_actions[next_index]
            self._next_indexes[point] = next_index + 1
            self._calls.append(point)

        # User-owned actions run outside synchronization. Their exact result or
        # BaseException propagates without wrapping, normalization, or retry.
        return action()
