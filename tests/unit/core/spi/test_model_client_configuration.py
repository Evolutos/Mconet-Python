"""Field tests for client defaults and direct component injection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    CompatibilityPolicy,
    Extensions,
    Headers,
    InteractionResourceLimits,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
)
from mconet.core.spi import (
    ModelClientConfiguration,
    MonitoringOptions,
    RuntimeComponents,
)


class _Target:
    """Structural target retained by identity."""

    def __init__(self) -> None:
        """Store the target fields required by the protocol."""
        self.service_id = OpenIdentifier("service.vendor")
        self.protocol_id = OpenIdentifier("protocol.vendor")
        self.model: ModelDescriptor = NamedModel("requested-model")
        self.deployment_id = None
        self.extensions: Extensions = MappingProxyType({})


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


def test_defaults_leave_every_client_field_unset() -> None:
    """Verify a new configuration supplies no client default."""
    configuration = ModelClientConfiguration()
    assert configuration.default_target is None
    assert configuration.default_service_access is None
    assert configuration.default_compatibility_policy is None
    assert configuration.default_resource_limits is None
    assert configuration.components is None
    assert configuration.monitoring_defaults is None
    assert not hasattr(configuration, "request_normalizers")


def test_each_default_and_injection_field_is_independent() -> None:
    """Verify setting one client field leaves the other defaults unset."""
    target = _Target()
    access = _Access()
    policy = CompatibilityPolicy(OpenIdentifier("strict"))
    limits = InteractionResourceLimits(max_response_body_bytes=1024)
    components = RuntimeComponents()
    monitoring = MonitoringOptions(capture_request_body=True)
    configuration = ModelClientConfiguration(
        default_target=cast(ModelTarget, target),
        default_service_access=cast(ServiceAccess, access),
        default_compatibility_policy=policy,
        default_resource_limits=limits,
        components=components,
        monitoring_defaults=monitoring,
    )
    assert configuration.default_target is target
    assert configuration.default_service_access is access
    assert configuration.default_compatibility_policy is policy
    assert configuration.default_resource_limits is limits
    assert configuration.components is components
    assert configuration.monitoring_defaults is monitoring

    only_components = ModelClientConfiguration(components=components)
    assert only_components.default_target is None
    assert only_components.monitoring_defaults is None
    assert only_components.components is components


def test_present_fields_must_use_their_nominal_types() -> None:
    """Reject a stand-in for each client configuration field."""
    cases: tuple[tuple[Callable[[], ModelClientConfiguration], str], ...] = (
        (
            lambda: ModelClientConfiguration(
                default_target=cast(ModelTarget, object())
            ),
            "default_target must be a ModelTarget or None.",
        ),
        (
            lambda: ModelClientConfiguration(
                default_service_access=cast(ServiceAccess, object())
            ),
            "default_service_access must be a ServiceAccess or None.",
        ),
        (
            lambda: ModelClientConfiguration(
                default_compatibility_policy=cast(CompatibilityPolicy, object())
            ),
            "default_compatibility_policy must be a CompatibilityPolicy or None.",
        ),
        (
            lambda: ModelClientConfiguration(
                default_resource_limits=cast(InteractionResourceLimits, object())
            ),
            "default_resource_limits must be an InteractionResourceLimits or None.",
        ),
        (
            lambda: ModelClientConfiguration(
                components=cast(RuntimeComponents, object())
            ),
            "components must be a RuntimeComponents or None.",
        ),
        (
            lambda: ModelClientConfiguration(
                monitoring_defaults=cast(MonitoringOptions, object())
            ),
            "monitoring_defaults must be a MonitoringOptions or None.",
        ),
    )
    for action, message in cases:
        try:
            action()
        except TypeError as error:
            assert message in str(error)
        else:
            raise AssertionError(f"Expected rejection containing {message}.")


def test_configuration_is_frozen() -> None:
    """Reject replacement of a stored client default."""
    configuration = ModelClientConfiguration()
    try:
        configuration.components = RuntimeComponents()  # type: ignore[misc]
    except FrozenInstanceError:
        assert configuration.components is None
        return
    raise AssertionError("Expected frozen client configuration.")
