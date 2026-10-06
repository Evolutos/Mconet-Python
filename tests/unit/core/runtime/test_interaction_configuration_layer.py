"""Internal data-boundary tests for InteractionConfigurationLayer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field, fields
from typing import cast

import mconet.core.domain
import mconet.core.runtime
from mconet.core.domain import (
    CancellationSignal,
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
    UriValue,
)
from mconet.core.domain.authorization import Authorization
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)

_EXPECTED_FIELDS = (
    "target",
    "service_access",
    "compatibility_policy",
    "resource_limits",
    "cancellation_signal",
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # A factory avoids sharing a mutable dict while the public annotation keeps
    # the extension boundary read-only to configuration consumers.
    return {}


def _noop_unsubscribe() -> None:
    """Provide an already-completed remover for the passive signal fixture."""
    # The fixture never has a pending callback, so removal has no state to change.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the field diagnostic so failure in another configuration dimension
    # cannot make a negative storage test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Custom structural target used to prove internal layers remain open."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Custom non-sensitive access object for complete-layer construction."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Signal:
    """Passive structural cancellation signal stored without activation."""

    @property
    def is_cancelled(self) -> bool:
        """Return the fixture's stable active state."""
        # The layer must store the reference without reading or changing state.
        return False

    @property
    def reason(self) -> str | None:
        """Return no reason while the passive fixture remains active."""
        # None is valid because is_cancelled independently reports active state.
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Return a completed remover without retaining the callback."""
        # The parameter remains intentionally unused: layer construction must not
        # subscribe, and this fixture has no cancellation source to trigger it.
        del callback
        return _noop_unsubscribe


def test_interaction_configuration_layer_defaults_every_field_to_absent() -> None:
    """Verify an empty source layer expresses no configuration overrides."""
    layer = InteractionConfigurationLayer()

    # None is preserved independently for every field so later merging can fall
    # through to lower-priority request, client, integration, or SDK sources.
    assert layer.target is None
    assert layer.service_access is None
    assert layer.compatibility_policy is None
    assert layer.resource_limits is None
    assert layer.cancellation_signal is None


def test_interaction_configuration_layer_stores_complete_valid_input() -> None:
    """Verify all supported data dimensions retain their original references."""
    target = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("model-a"),
    )
    service_access = _Access(endpoint=UriValue("https://example.test", True))
    policy = CompatibilityPolicy(OpenIdentifier("compatible"))
    resource_limits = InteractionResourceLimits(max_frame_bytes=1_024)
    signal = _Signal()

    layer = InteractionConfigurationLayer(
        target=target,
        service_access=service_access,
        compatibility_policy=policy,
        resource_limits=resource_limits,
        cancellation_signal=signal,
    )

    # Internal layering is non-normalizing: it stores each explicit input for a
    # later merger without resolving, validating semantics, or subscribing.
    assert layer.target is target
    assert layer.service_access is service_access
    assert layer.compatibility_policy is policy
    assert layer.resource_limits is resource_limits
    assert layer.cancellation_signal is signal


def test_interaction_configuration_layer_contains_only_mergeable_fields() -> None:
    """Verify components and monitoring behavior cannot enter the data layer."""
    field_names = tuple(field.name for field in fields(InteractionConfigurationLayer))

    # An exact field contract prevents this internal carrier from becoming a
    # second RuntimeComponents, MonitoringOptions, or public Options container.
    assert field_names == _EXPECTED_FIELDS


def test_interaction_configuration_layer_defers_semantic_validation() -> None:
    """Verify the carrier preserves unresolved values for the later validator."""
    unresolved_limits = InteractionResourceLimits(max_frame_bytes=0)

    layer = InteractionConfigurationLayer(resource_limits=unresolved_limits)

    # Nominal storage is enforced here, but zero remains observable so the shared
    # resource validator can produce the stable field-specific validation error.
    stored_limits = layer.resource_limits
    assert stored_limits is unresolved_limits
    assert stored_limits is not None
    assert stored_limits.max_frame_bytes == 0


def test_interaction_configuration_layer_is_internal_and_immutable() -> None:
    """Verify the layer is not exported and cannot be modified after creation."""
    layer = InteractionConfigurationLayer()

    # Both package export surfaces remain empty of the internal carrier, while
    # frozen storage prevents a merge from writing values back into source layers.
    assert "InteractionConfigurationLayer" not in mconet.core.runtime.__all__
    assert "InteractionConfigurationLayer" not in mconet.core.domain.__all__
    _assert_raises(
        FrozenInstanceError,
        lambda: layer.__setattr__(
            "compatibility_policy",
            CompatibilityPolicy(OpenIdentifier("strict")),
        ),
        "cannot assign to field",
    )


def test_interaction_configuration_layer_rejects_invalid_field_types() -> None:
    """Verify every optional dimension enforces its nominal storage boundary."""
    invalid_layers = (
        (
            lambda: InteractionConfigurationLayer(target=cast(ModelTarget, object())),
            "target must implement ModelTarget",
        ),
        (
            lambda: InteractionConfigurationLayer(
                service_access=cast(ServiceAccess, object())
            ),
            "service_access must implement ServiceAccess",
        ),
        (
            lambda: InteractionConfigurationLayer(
                compatibility_policy=cast(CompatibilityPolicy, object())
            ),
            "compatibility_policy must be CompatibilityPolicy",
        ),
        (
            lambda: InteractionConfigurationLayer(
                resource_limits=cast(InteractionResourceLimits, object())
            ),
            "resource_limits must be InteractionResourceLimits",
        ),
        (
            lambda: InteractionConfigurationLayer(
                cancellation_signal=cast(CancellationSignal, object())
            ),
            "cancellation_signal must implement CancellationSignal",
        ),
    )

    # Fields fail independently so later merge failures identify the exact source
    # dimension instead of surfacing as an unrelated attribute error.
    for create_layer, message in invalid_layers:
        _assert_raises(TypeError, create_layer, message)
