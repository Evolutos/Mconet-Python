"""Field tests for one interaction's overrides."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    CancellationSignal,
    CompatibilityPolicy,
    Extensions,
    Headers,
    InteractionResourceLimits,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
)
from mconet.core.spi import InteractionOptions, MonitoringOptions, RuntimeComponents


class _Access:
    """Structural access retained by identity."""

    def __init__(self) -> None:
        """Store the access fields required by the protocol."""
        self.endpoint = None
        self.authorization = None
        self.headers = Headers()
        self.query = QueryParameters()
        self.api_version = None
        self.project_id = None
        self.tenant_id = None
        self.extensions: Extensions = MappingProxyType({})


class _Signal:
    """Cancellation signal that must not be subscribed during construction."""

    def __init__(self) -> None:
        """Store idle cancellation facts."""
        self.is_cancelled = False
        self.reason = None
        self.calls: list[str] = []

    def subscribe(self, callback: object) -> Callable[[], None]:
        """Record a subscription that option construction must not make."""
        del callback
        self.calls.append("subscribe")
        return lambda: None


def test_defaults_leave_overrides_unset_and_raw_response_off() -> None:
    """Verify one interaction starts without overrides or a raw response."""
    options = InteractionOptions()
    assert options.components is None
    assert options.service_access_override is None
    assert options.compatibility_policy is None
    assert options.resource_limits is None
    assert options.monitoring_options is None
    assert options.cancellation_signal is None
    assert options.include_raw_response is False
    assert not hasattr(options, "request_normalizers")


def test_each_override_is_independent_and_not_subscribed() -> None:
    """Verify one supplied field leaves the other overrides unset."""
    components = RuntimeComponents()
    access = _Access()
    policy = CompatibilityPolicy(OpenIdentifier("strict"))
    limits = InteractionResourceLimits(max_response_body_bytes=32)
    monitoring = MonitoringOptions()
    signal = _Signal()
    options = InteractionOptions(
        components=components,
        service_access_override=cast(ServiceAccess, access),
        compatibility_policy=policy,
        resource_limits=limits,
        monitoring_options=monitoring,
        cancellation_signal=cast(CancellationSignal, signal),
        include_raw_response=True,
    )
    assert options.components is components
    assert options.service_access_override is access
    assert options.compatibility_policy is policy
    assert options.resource_limits is limits
    assert options.monitoring_options is monitoring
    assert options.cancellation_signal is signal
    assert options.include_raw_response is True
    assert signal.calls == []

    only_signal = InteractionOptions(
        cancellation_signal=cast(CancellationSignal, signal)
    )
    assert only_signal.components is None
    assert only_signal.include_raw_response is False
    assert signal.calls == []


def test_present_overrides_must_use_their_nominal_types() -> None:
    """Reject a stand-in for each interaction override."""
    cases: tuple[tuple[Callable[[], InteractionOptions], str], ...] = (
        (
            lambda: InteractionOptions(components=cast(RuntimeComponents, object())),
            "components must be a RuntimeComponents or None.",
        ),
        (
            lambda: InteractionOptions(
                service_access_override=cast(ServiceAccess, object())
            ),
            "service_access_override must be a ServiceAccess or None.",
        ),
        (
            lambda: InteractionOptions(
                compatibility_policy=cast(CompatibilityPolicy, object())
            ),
            "compatibility_policy must be a CompatibilityPolicy or None.",
        ),
        (
            lambda: InteractionOptions(
                resource_limits=cast(InteractionResourceLimits, object())
            ),
            "resource_limits must be an InteractionResourceLimits or None.",
        ),
        (
            lambda: InteractionOptions(
                monitoring_options=cast(MonitoringOptions, object())
            ),
            "monitoring_options must be a MonitoringOptions or None.",
        ),
        (
            lambda: InteractionOptions(
                cancellation_signal=cast(CancellationSignal, object())
            ),
            "cancellation_signal must be a CancellationSignal or None.",
        ),
        (
            lambda: InteractionOptions(include_raw_response=cast(bool, 1)),
            "include_raw_response must be a bool.",
        ),
    )
    for action, message in cases:
        try:
            action()
        except TypeError as error:
            assert message in str(error)
        else:
            raise AssertionError(f"Expected rejection containing {message}.")


def test_options_are_frozen() -> None:
    """Reject assignment of an interaction override after construction."""
    options = InteractionOptions()
    try:
        options.include_raw_response = True  # type: ignore[misc]
    except FrozenInstanceError:
        assert options.include_raw_response is False
        return
    raise AssertionError("Expected frozen interaction options.")
