"""Combination and boundary tests for per-interaction transport context."""

import math
import operator
from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import (
    CancellationSignal,
    Extensions,
    JsonValue,
    ResolvedInteractionResourceLimits,
    Timestamp,
)
from mconet.core.spi import TransportContext


class _ControllableSignal:
    """Minimal structural cancellation signal with an external control method."""

    def __init__(self) -> None:
        """Create active cancellation state without subscribers."""
        # Integer keys let each returned remover target one callback without
        # relying on callable identity or exposing storage through the protocol.
        self._next_subscription = 0
        self._callbacks: dict[int, Callable[[str | None], None]] = {}
        self._is_cancelled = False
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether external control has applied its first cancellation."""
        # Observation is read-only and does not consume or acknowledge the state.
        return self._is_cancelled

    @property
    def reason(self) -> str | None:
        """Return the stable first cancellation reason when present."""
        # Active state and cancellation without a reason are distinguished by
        # is_cancelled while both correctly expose None here.
        return self._reason

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Register one callback or notify it immediately after cancellation."""
        # Late subscription cannot miss a transition that happened before the
        # transport began observing the context.
        if self._is_cancelled:
            callback(self._reason)
            return _noop_unsubscribe

        subscription = self._next_subscription
        self._next_subscription += 1
        self._callbacks[subscription] = callback
        is_active = True

        def unsubscribe() -> None:
            """Remove this callback once and make later removals no-ops."""
            nonlocal is_active
            # Clear the closure guard before storage so reentrant cleanup cannot
            # observe or remove the same subscription twice.
            if not is_active:
                return
            is_active = False
            self._callbacks.pop(subscription, None)

        return unsubscribe

    def cancel(self, reason: str | None = None) -> None:
        """Apply the first cancellation and notify pending subscribers once."""
        # First-writer-wins preserves both state and reason; repeated application
        # returns before issuing duplicate callbacks.
        if self._is_cancelled:
            return
        self._is_cancelled = True
        self._reason = reason
        callbacks = tuple(self._callbacks.values())
        self._callbacks.clear()

        # Clear shared storage before invoking application callbacks so reentrant
        # unsubscription or cancellation cannot produce a second delivery.
        for callback in callbacks:
            callback(reason)


def _noop_unsubscribe() -> None:
    """Represent cleanup for a subscription already notified synchronously."""
    # The stateless function is safely reusable because it owns no pending entry.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable field-specific diagnostics prevent incidental protocol or fixture
        # failures from making a negative context test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _limits(frame_bytes: int = 512) -> ResolvedInteractionResourceLimits:
    """Build complete finite limits for one context fixture."""
    # Distinct values make identity and equality failures easier to attribute to
    # the exact resource consumer represented by each field.
    return ResolvedInteractionResourceLimits(4_096, 1_024, frame_bytes)


def test_transport_context_preserves_complete_interaction_inputs() -> None:
    """Verify ID, limits, deadline, signal, and extensions remain exact."""
    limits = _limits()
    deadline = Timestamp(1_800_000_000, 123_456_789)
    cancellation = _ControllableSignal()

    context = TransportContext(
        "interaction-7",
        limits,
        deadline=deadline,
        cancellation=cancellation,
        extensions={"vendor.region": "east", "vendor.attempt": 1},
    )

    # Structured inputs retain identity; context construction never recalculates
    # a deadline, copies cancellation state, or resolves resource defaults again.
    assert context.interaction_id == "interaction-7"
    assert context.resource_limits is limits
    assert context.deadline is deadline
    assert context.cancellation is cancellation
    assert context.extensions == {"vendor.region": "east", "vendor.attempt": 1}


def test_transport_context_preserves_absent_optional_controls() -> None:
    """Verify missing deadline and cancellation remain independently absent."""
    context = TransportContext("interaction-8", _limits())

    # None is not replaced by a current timestamp or a shared cancellation source;
    # the default extension mapping is concretely empty and read-only.
    assert context.deadline is None
    assert context.cancellation is None
    assert context.extensions == {}
    assert not hasattr(context.extensions, "__setitem__")


def test_transport_context_does_not_interpret_deadline_or_cancellation() -> None:
    """Verify context stores absolute time and live signal without control effects."""
    deadline = Timestamp(-1, 999_999_999)
    cancellation = _ControllableSignal()
    cancellation.cancel("caller_requested")

    context = TransportContext(
        "interaction-9",
        _limits(),
        deadline=deadline,
        cancellation=cancellation,
    )
    reasons: list[str | None] = []
    context_cancellation = context.cancellation
    assert context_cancellation is not None
    assert context_cancellation is cancellation
    context_cancellation.subscribe(reasons.append)

    # A past instant is still a valid absolute fact for the scheduler to assess,
    # and a pre-cancelled structural signal preserves immediate notification.
    assert context.deadline is deadline
    assert context_cancellation.is_cancelled
    assert context_cancellation.reason == "caller_requested"
    assert reasons == ["caller_requested"]


def test_transport_context_freezes_extension_membership() -> None:
    """Verify portable context extensions detach from caller mapping changes."""
    source: dict[str, JsonValue] = {
        "vendor.route": {"zone": "a"},
        "vendor.weight": 0.5,
    }
    context = TransportContext("interaction-10", _limits(), extensions=source)
    source["later"] = False

    # Only original membership appears through a read-only proxy; nested portable
    # JSON values remain exact rather than being interpreted by the context.
    assert context.extensions == {
        "vendor.route": {"zone": "a"},
        "vendor.weight": 0.5,
    }
    assert "later" not in context.extensions
    _assert_raises(
        TypeError,
        lambda: operator.setitem(
            cast(MutableMapping[str, JsonValue], context.extensions),
            "vendor.new",
            1,
        ),
        "does not support item assignment",
    )


def test_transport_context_has_complete_frozen_value_semantics() -> None:
    """Verify equality, owned field surface, and frozen replacement behavior."""
    first = TransportContext("interaction-11", _limits(), Timestamp(100))
    same = TransportContext("interaction-11", _limits(), Timestamp(100))
    different = TransportContext("interaction-11", _limits(513), Timestamp(100))

    # All five fields participate in equality, while frozen slots prevent one
    # consumer from replacing limits after another consumer observes the context.
    assert first == same
    assert first != different
    assert tuple(field.name for field in fields(TransportContext)) == (
        "interaction_id",
        "resource_limits",
        "deadline",
        "cancellation",
        "extensions",
    )
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("resource_limits", _limits(1_024)),
        "cannot assign to field",
    )


def test_transport_context_requires_id_and_resolved_limits() -> None:
    """Verify required interaction facts reject primitive and unresolved substitutes."""
    # ID remains exact text, and limits must be the complete resolved value rather
    # than a dict, optional configuration object, or absent sentinel.
    _assert_raises(
        TypeError,
        lambda: TransportContext(cast(str, 7), _limits()),
        "interaction_id must be a string",
    )
    for value in ({"max_response_body_bytes": 100}, None, object()):
        _assert_raises(
            TypeError,
            lambda value=value: TransportContext(
                "interaction-12",
                cast(ResolvedInteractionResourceLimits, value),
            ),
            "resource_limits must be a ResolvedInteractionResourceLimits",
        )


def test_transport_context_rejects_invalid_optional_control_types() -> None:
    """Verify deadline and cancellation accept only their established contracts."""
    # Integer epochs, timestamp text, and incomplete cancellation-like objects
    # are not silently converted because that would change precision or lifecycle.
    for value in (1_800_000_000, "2030-01-01T00:00:00Z", object()):
        _assert_raises(
            TypeError,
            lambda value=value: TransportContext(
                "interaction-13", _limits(), deadline=cast(Timestamp, value)
            ),
            "deadline must be a Timestamp or None",
        )

    class _StateOnlySignal:
        """Intentionally omit subscription from cancellation-shaped state."""

        # State properties alone cannot propagate a transition that occurs after
        # transport work starts, so this fixture must fail structural recognition.
        is_cancelled = False
        reason: str | None = None

    _assert_raises(
        TypeError,
        lambda: TransportContext(
            "interaction-13",
            _limits(),
            cancellation=cast(CancellationSignal, _StateOnlySignal()),
        ),
        "cancellation must implement CancellationSignal or be None",
    )


def test_transport_context_rejects_invalid_extensions() -> None:
    """Verify extensions obey mapping and portable recursive JSON constraints."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    invalid_cases: tuple[tuple[Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, []), TypeError, "extensions must be a mapping"),
        (cast(Extensions, {1: "bad"}), TypeError, "extensions keys must be strings"),
        (
            cast(Extensions, {"bad": object()}),
            TypeError,
            "structurally valid JsonValue",
        ),
        (
            {"bad": math.nan},
            ValueError,
            "floating-point value must be finite",
        ),
        (
            {"bad": cyclic},
            TypeError,
            "structurally valid JsonValue",
        ),
    )

    # Invalid containers, keys, nested values, numbers, and cycles all fail before
    # a partially valid context can reach transport code.
    for extensions, exception_type, message in invalid_cases:
        _assert_raises(
            exception_type,
            lambda extensions=extensions: TransportContext(
                "interaction-14", _limits(), extensions=extensions
            ),
            message,
        )
