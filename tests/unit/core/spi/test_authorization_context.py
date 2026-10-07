"""Non-sensitive boundary tests for immutable authorization context values."""

from __future__ import annotations

import math
import operator
from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, dataclass, field, fields
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    SecretValue,
    Timestamp,
    UriValue,
)
from mconet.core.spi import AuthorizationContext, BodySigningMode


def _empty_extensions() -> Extensions:
    """Create independent portable extension storage for target fixtures."""
    # A fresh mapping prevents unrelated targets from sharing caller-owned
    # mutable membership before AuthorizationContext validates the target.
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target used by authorization fixtures."""

    service_id: OpenIdentifier
    """Open model-service identity."""

    protocol_id: OpenIdentifier
    """Open interaction-protocol identity."""

    model: ModelDescriptor
    """Exact model descriptor selected for this interaction."""

    deployment_id: str | None = None
    """Optional service deployment identity."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable target fields retained for future integrations."""


class _ControllableSignal:
    """Read-only signal fixture with a test-owned cancellation operation."""

    def __init__(self) -> None:
        """Create active cancellation state with no pending callbacks."""
        # Integer subscription keys allow each remover to target exactly one
        # callback without exposing mutable storage through the public protocol.
        self._next_subscription = 0
        self._callbacks: dict[int, Callable[[str | None], None]] = {}
        self._is_cancelled = False
        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether the first external cancellation has occurred."""
        # Observation never consumes the transition or changes callback state.
        return self._is_cancelled

    @property
    def reason(self) -> str | None:
        """Return the stable first cancellation reason when present."""
        # Active state and cancellation without a reason remain distinguishable
        # through is_cancelled while both correctly expose None here.
        return self._reason

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Register one callback or notify it immediately after cancellation."""
        # Late subscribers cannot miss a transition that occurs before a
        # credential source begins authorization work.
        if self._is_cancelled:
            callback(self._reason)
            return _noop_unsubscribe

        subscription = self._next_subscription
        self._next_subscription += 1
        self._callbacks[subscription] = callback
        is_active = True

        def unsubscribe() -> None:
            """Remove this pending callback once and make later calls no-ops."""
            nonlocal is_active
            # Clear the guard before shared storage so reentrant cleanup cannot
            # remove or observe the same pending subscription twice.
            if not is_active:
                return
            is_active = False
            self._callbacks.pop(subscription, None)

        return unsubscribe

    def cancel(self, reason: str | None = None) -> None:
        """Apply the first cancellation and notify pending subscribers once."""
        # First-writer-wins keeps state and reason stable across repeated calls.
        if self._is_cancelled:
            return
        self._is_cancelled = True
        self._reason = reason
        callbacks = tuple(self._callbacks.values())
        self._callbacks.clear()

        # Empty storage before invoking application callbacks so reentrant
        # cancellation or unsubscribe calls cannot produce duplicate delivery.
        for callback in callbacks:
            callback(reason)


def _noop_unsubscribe() -> None:
    """Represent cleanup for a callback already notified synchronously."""
    # The stateless function owns no pending callback and is safely repeatable.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise one expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable context-owned wording keeps malformed fixtures from satisfying
        # an unrelated negative field assertion accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _target(**changes: object) -> _Target:
    """Build one valid target while allowing focused boundary replacements."""
    # NamedModel uses the production descriptor implementation so context tests
    # exercise the complete existing target validator rather than a loose mock.
    values: dict[str, object] = {
        "service_id": OpenIdentifier("service.example"),
        "protocol_id": OpenIdentifier("protocol.example"),
        "model": NamedModel("model-example"),
        "deployment_id": "deployment-a",
        "extensions": {"provider.region": "test-region"},
    }
    values.update(changes)
    return _Target(
        service_id=cast(OpenIdentifier, values["service_id"]),
        protocol_id=cast(OpenIdentifier, values["protocol_id"]),
        model=cast(ModelDescriptor, values["model"]),
        deployment_id=cast(str | None, values["deployment_id"]),
        extensions=cast(Extensions, values["extensions"]),
    )


def _context(**changes: object) -> AuthorizationContext:
    """Build one complete context while allowing focused field replacements."""
    # Central valid data keeps negative tests attributable to the single field
    # they replace and makes every required context fact visible in one fixture.
    values: dict[str, object] = {
        "interaction_id": "interaction-7",
        "target": _target(),
        "endpoint": UriValue("https://models.example.test/v1", True),
        "transport_kind": OpenIdentifier("http"),
        "timestamp": Timestamp(1_800_000_000, 123_456_789),
        "body_signing_mode": "none",
        "cancellation": None,
        "extensions": {"authorization.region": "east"},
    }
    values.update(changes)
    return AuthorizationContext(
        interaction_id=cast(str, values["interaction_id"]),
        target=cast(ModelTarget, values["target"]),
        endpoint=cast(UriValue, values["endpoint"]),
        transport_kind=cast(OpenIdentifier, values["transport_kind"]),
        timestamp=cast(Timestamp, values["timestamp"]),
        body_signing_mode=cast(BodySigningMode, values["body_signing_mode"]),
        cancellation=cast(_ControllableSignal | None, values["cancellation"]),
        extensions=cast(Extensions, values["extensions"]),
    )


def test_authorization_context_preserves_complete_resolved_facts() -> None:
    """Retain every required non-sensitive value without reinterpretation."""
    target = _target()
    endpoint = UriValue("https://models.example.test/v1", True)
    transport_kind = OpenIdentifier("transport.http")
    timestamp = Timestamp(1_800_000_000, 123_456_789)

    context = _context(
        target=target,
        endpoint=endpoint,
        transport_kind=transport_kind,
        timestamp=timestamp,
        body_signing_mode="precomputed_digest",
    )

    # Structured facts retain identity, while scalar identity and signing mode
    # remain exact; construction does not resolve access or sample another time.
    assert context.interaction_id == "interaction-7"
    assert context.target is target
    assert context.endpoint is endpoint
    assert context.transport_kind is transport_kind
    assert context.timestamp is timestamp
    assert context.body_signing_mode == "precomputed_digest"
    assert context.cancellation is None
    assert context.extensions == {"authorization.region": "east"}


def test_authorization_context_accepts_every_defined_signing_mode() -> None:
    """Preserve the closed architecture modes selected by later resolution."""
    modes: tuple[BodySigningMode, ...] = (
        "none",
        "precomputed_digest",
        "unsigned_payload",
        "buffered_digest",
        "chunked_signature",
    )

    # This value records a selected mode without negotiating it. A separate
    # runtime guard rejects modes outside the enabled release profile.
    contexts = tuple(_context(body_signing_mode=mode) for mode in modes)
    assert tuple(context.body_signing_mode for context in contexts) == modes


def test_authorization_context_observes_live_optional_cancellation() -> None:
    """Keep a structural signal by identity without controlling its state."""
    signal = _ControllableSignal()
    context = _context(cancellation=signal)
    reasons: list[str | None] = []
    context_cancellation = context.cancellation
    assert context_cancellation is signal
    assert context_cancellation is not None
    context_cancellation.subscribe(reasons.append)

    signal.cancel("caller_requested")

    # Cancellation after construction remains visible because the context owns
    # no copied Boolean, controller operation, or alternate subscription state.
    assert context_cancellation.is_cancelled
    assert context_cancellation.reason == "caller_requested"
    assert reasons == ["caller_requested"]


def test_authorization_context_has_exact_non_sensitive_frozen_surface() -> None:
    """Expose only documented safe facts and reject field replacement."""
    context = _context()

    # Exact fields prevent authorization configuration, credentials, request
    # components, or mutable request state from entering this shared context.
    assert tuple(field.name for field in fields(AuthorizationContext)) == (
        "interaction_id",
        "target",
        "endpoint",
        "transport_kind",
        "timestamp",
        "body_signing_mode",
        "cancellation",
        "extensions",
    )
    for forbidden in (
        "authorization",
        "credential",
        "headers",
        "query",
        "body",
        "request",
        "mutable_request",
    ):
        assert not hasattr(context, forbidden)
    _assert_raises(
        FrozenInstanceError,
        lambda: context.__setattr__("endpoint", context.endpoint),
        "cannot assign to field",
    )


def test_authorization_context_validates_nominal_fields() -> None:
    """Reject malformed required values at their own context boundaries."""
    invalid_values = (
        ("interaction_id", 7, TypeError, "interaction_id must be a string"),
        ("target", object(), TypeError, "target must implement ModelTarget"),
        ("endpoint", "https://example.test", TypeError, "endpoint must be a UriValue"),
        (
            "transport_kind",
            "http",
            TypeError,
            "transport_kind must be an OpenIdentifier",
        ),
        ("timestamp", 1_800_000_000, TypeError, "timestamp must be a Timestamp"),
        ("body_signing_mode", 1, TypeError, "body_signing_mode must be a string"),
        (
            "body_signing_mode",
            "vendor_mode",
            ValueError,
            "body_signing_mode is unsupported",
        ),
        (
            "cancellation",
            object(),
            TypeError,
            "cancellation must implement CancellationSignal",
        ),
    )

    # Default arguments keep every other field valid, so each error proves one
    # exact runtime boundary rather than a broad construction failure.
    for field_name, value, error_type, message in invalid_values:
        _assert_raises(
            error_type,
            lambda field_name=field_name, value=value: _context(**{field_name: value}),
            message,
        )


def test_authorization_context_requires_valid_absolute_endpoint() -> None:
    """Reject relative and syntactically invalid authorization endpoints."""
    # Signing needs a resolved origin and canonical request target; a relative
    # reference or malformed percent escape cannot supply either safely.
    _assert_raises(
        ValueError,
        lambda: _context(endpoint=UriValue("v1/models", False)),
        "endpoint must be absolute",
    )
    _assert_raises(
        ValueError,
        lambda: _context(endpoint=UriValue("https://example.test/%ZZ", True)),
        "invalid percent escape",
    )


def test_authorization_context_validates_target_non_sensitive_data() -> None:
    """Prevent secret wrappers from entering through target extensions."""
    target = _target(extensions=cast(Extensions, {"credential": SecretValue("secret")}))

    # ModelTarget is structurally open, so explicit semantic validation is needed
    # before its extension channel crosses the authorization context boundary.
    _assert_raises(
        TypeError,
        lambda: _context(target=target),
        "structurally valid JsonValue",
    )


def test_authorization_context_freezes_portable_extensions() -> None:
    """Detach extension membership and reject opaque or invalid values."""
    source: dict[str, JsonValue] = {"region": "east", "attempt": 1}
    context = _context(extensions=source)
    source["late"] = True

    # The context observes a stable read-only top-level mapping; recursive JSON
    # validation prevents extensions from bypassing the non-sensitive boundary.
    assert context.extensions == {"region": "east", "attempt": 1}
    _assert_raises(
        TypeError,
        lambda: operator.setitem(
            cast(MutableMapping[str, JsonValue], context.extensions),
            "changed",
            True,
        ),
        "does not support item assignment",
    )

    invalid_extensions: tuple[object, ...] = (
        [],
        {1: "non-string-key"},
        {"secret": SecretValue("secret")},
        {"number": math.inf},
    )
    for extensions in invalid_extensions:
        try:
            _context(extensions=extensions)
        except (TypeError, ValueError):
            continue
        raise AssertionError("Expected invalid authorization extensions to fail.")
