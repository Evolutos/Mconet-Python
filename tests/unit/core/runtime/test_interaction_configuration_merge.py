"""Deterministic precedence tests for interaction configuration merging."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import mconet.core.runtime
from mconet.core.domain import (
    Authorization,
    CompatibilityPolicy,
    Extensions,
    Headers,
    InteractionResourceLimits,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    UriValue,
)
from mconet.core.runtime.interaction_configuration_layer import (
    InteractionConfigurationLayer,
)
from mconet.core.runtime.interaction_configuration_merge import (
    merge_interaction_configuration,
)
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)

_SDK_LIMITS = ResolvedInteractionResourceLimits(100, 200, 300)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Each fixture owns its mapping so tests never rely on shared mutable state
    # while the public protocol still exposes a read-only mapping annotation.
    return {}


def _noop_unsubscribe() -> None:
    """Provide an already-completed remover for the passive signal fixture."""
    # The signal fixture stores no callback, so removal has no state to change.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Matching the source diagnostic prevents an unrelated merge failure from
    # making a negative layer or completeness test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Custom structural target carrying a source marker in its model name."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Custom non-sensitive access value carrying a source-specific endpoint."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Signal:
    """Passive structural cancellation signal with an observable source marker."""

    marker: str

    @property
    def is_cancelled(self) -> bool:
        """Return the fixture's stable active state."""
        # Merging must retain the signal without inspecting or changing state.
        return False

    @property
    def reason(self) -> str | None:
        """Return no reason while the fixture remains active."""
        # Activity is represented separately, so None does not imply cancellation.
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Return a completed remover without retaining the callback."""
        # The passive fixture has no source; deleting the argument makes the lack
        # of registration explicit and keeps construction side-effect free.
        del callback
        return _noop_unsubscribe


def _target(source: str) -> _Target:
    """Create one structural target whose immutable model identifies its source."""
    # Stable service and protocol identifiers isolate precedence assertions to
    # object identity and model marker rather than unrelated validation details.
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel(f"model-{source}"),
    )


def _access(source: str) -> _Access:
    """Create one structural access value with a distinct absolute endpoint."""
    # The endpoint marker makes fallback failures readable without introducing
    # Authorization or Secret state into ordinary precedence tests.
    return _Access(endpoint=UriValue(f"https://{source}.example.test", True))


def _policy(mode: str) -> CompatibilityPolicy:
    """Create one immutable compatibility policy for source-selection tests."""
    # OpenIdentifier permits both standard and future modes; no closed enum is
    # introduced merely to distinguish fixture sources.
    return CompatibilityPolicy(OpenIdentifier(mode))


def _merge(
    *,
    interaction: InteractionConfigurationLayer | None = None,
    request: InteractionConfigurationLayer | None = None,
    client: InteractionConfigurationLayer | None = None,
    integration: InteractionConfigurationLayer | None = None,
    sdk_limits: ResolvedInteractionResourceLimits = _SDK_LIMITS,
) -> ResolvedInteractionConfiguration:
    """Merge optional test inputs after materializing absent source layers."""
    # Empty immutable layers express source absence through the same production
    # carrier instead of bypassing the required merger boundary with None.
    # Explicit identity checks avoid treating a future false-valued layer as absent.
    return merge_interaction_configuration(
        interaction_layer=(
            interaction if interaction is not None else InteractionConfigurationLayer()
        ),
        request_layer=(
            request if request is not None else InteractionConfigurationLayer()
        ),
        client_layer=(
            client if client is not None else InteractionConfigurationLayer()
        ),
        integration_layer=(
            integration if integration is not None else InteractionConfigurationLayer()
        ),
        sdk_resource_limits=sdk_limits,
    )


def test_configuration_merger_selects_every_highest_priority_source() -> None:
    """Verify all resolved fields use their highest applicable populated source."""
    interaction_target = _target("interaction")
    request_target = _target("request")
    client_target = _target("client")
    integration_target = _target("integration")
    interaction_access = _access("interaction")
    signal = _Signal("interaction")

    resolved = _merge(
        interaction=InteractionConfigurationLayer(
            target=interaction_target,
            service_access=interaction_access,
            compatibility_policy=_policy("strict"),
            resource_limits=InteractionResourceLimits(111, 222, 333),
            cancellation_signal=signal,
        ),
        request=InteractionConfigurationLayer(
            target=request_target,
            service_access=_access("request"),
            compatibility_policy=_policy("request-policy"),
            resource_limits=InteractionResourceLimits(444, 555, 666),
            cancellation_signal=_Signal("request"),
        ),
        client=InteractionConfigurationLayer(
            target=client_target,
            service_access=_access("client"),
            compatibility_policy=_policy("compatible"),
            resource_limits=InteractionResourceLimits(777, 888, 999),
            cancellation_signal=_Signal("client"),
        ),
        integration=InteractionConfigurationLayer(
            target=integration_target,
            service_access=_access("integration"),
            compatibility_policy=_policy("integration-policy"),
            resource_limits=InteractionResourceLimits(1_000, 1_001, 1_002),
            cancellation_signal=_Signal("integration"),
        ),
    )

    # Field-specific source applicability matters as much as layer order:
    # interaction target is ignored, while its access, policy, limits, and signal
    # are the highest valid sources for those dimensions.
    assert resolved.target is request_target
    assert resolved.service_access is interaction_access
    assert resolved.compatibility_policy == _policy("strict")
    assert resolved.resource_limits == ResolvedInteractionResourceLimits(
        111,
        222,
        333,
    )
    assert resolved.cancellation_signal is signal


def test_configuration_merger_falls_through_every_access_source() -> None:
    """Verify access selects interaction, Request, Client, integration, then None."""
    interaction_access = _access("interaction")
    request_access = _access("request")
    client_access = _access("client")
    integration_access = _access("integration")
    request_target = _target("request")
    cases = (
        (
            InteractionConfigurationLayer(service_access=interaction_access),
            InteractionConfigurationLayer(
                target=request_target,
                service_access=request_access,
            ),
            InteractionConfigurationLayer(service_access=client_access),
            InteractionConfigurationLayer(service_access=integration_access),
            interaction_access,
        ),
        (
            InteractionConfigurationLayer(),
            InteractionConfigurationLayer(
                target=request_target,
                service_access=request_access,
            ),
            InteractionConfigurationLayer(service_access=client_access),
            InteractionConfigurationLayer(service_access=integration_access),
            request_access,
        ),
        (
            InteractionConfigurationLayer(),
            InteractionConfigurationLayer(target=request_target),
            InteractionConfigurationLayer(service_access=client_access),
            InteractionConfigurationLayer(service_access=integration_access),
            client_access,
        ),
        (
            InteractionConfigurationLayer(),
            InteractionConfigurationLayer(target=request_target),
            InteractionConfigurationLayer(),
            InteractionConfigurationLayer(service_access=integration_access),
            integration_access,
        ),
        (
            InteractionConfigurationLayer(),
            InteractionConfigurationLayer(target=request_target),
            InteractionConfigurationLayer(),
            InteractionConfigurationLayer(),
            None,
        ),
    )

    # Each row removes one higher-priority explicit value, proving absence falls
    # through exactly one tier and that complete absence remains representable.
    for interaction, request, client, integration, expected in cases:
        resolved = _merge(
            interaction=interaction,
            request=request,
            client=client,
            integration=integration,
        )
        assert resolved.service_access is expected


def test_configuration_merger_uses_request_then_client_target() -> None:
    """Verify Request target wins and Client supplies the only valid fallback."""
    request_target = _target("request")
    client_target = _target("client")
    integration_target = _target("integration")

    request_resolved = _merge(
        request=InteractionConfigurationLayer(target=request_target),
        client=InteractionConfigurationLayer(target=client_target),
        integration=InteractionConfigurationLayer(target=integration_target),
    )
    client_resolved = _merge(
        client=InteractionConfigurationLayer(target=client_target),
        integration=InteractionConfigurationLayer(target=integration_target),
    )

    # Integration target is deliberately inapplicable; it cannot silently turn
    # an access binding into a default model selection.
    assert request_resolved.target is request_target
    assert client_resolved.target is client_target


def test_configuration_merger_rejects_missing_request_and_client_target() -> None:
    """Verify an inapplicable interaction or integration target cannot fill output."""
    interaction = InteractionConfigurationLayer(target=_target("interaction"))
    integration = InteractionConfigurationLayer(target=_target("integration"))

    # Resolved configuration requires a target, and its only defined sources are
    # Request and Client; semantic validation of a selected target remains later.
    _assert_raises(
        ValueError,
        lambda: _merge(interaction=interaction, integration=integration),
        "target must be provided by request_layer or client_layer",
    )


def test_configuration_merger_falls_through_policy_sources() -> None:
    """Verify policy selects interaction, Client, then the compatible SDK default."""
    target = _target("request")
    interaction_policy = _policy("strict")
    client_policy = _policy("permissive")
    request_policy = _policy("request-policy")
    integration_policy = _policy("integration-policy")

    interaction_resolved = _merge(
        interaction=InteractionConfigurationLayer(
            compatibility_policy=interaction_policy
        ),
        request=InteractionConfigurationLayer(
            target=target,
            compatibility_policy=request_policy,
        ),
        client=InteractionConfigurationLayer(compatibility_policy=client_policy),
        integration=InteractionConfigurationLayer(
            compatibility_policy=integration_policy
        ),
    )
    client_resolved = _merge(
        request=InteractionConfigurationLayer(
            target=target,
            compatibility_policy=request_policy,
        ),
        client=InteractionConfigurationLayer(compatibility_policy=client_policy),
        integration=InteractionConfigurationLayer(
            compatibility_policy=integration_policy
        ),
    )
    default_resolved = _merge(
        request=InteractionConfigurationLayer(
            target=target,
            compatibility_policy=request_policy,
        ),
        integration=InteractionConfigurationLayer(
            compatibility_policy=integration_policy
        ),
    )

    # Request and integration policies are intentionally ignored because neither
    # is a policy source; total absence resolves through the stable public factory.
    assert interaction_resolved.compatibility_policy is interaction_policy
    assert client_resolved.compatibility_policy is client_policy
    assert str(default_resolved.compatibility_policy) == "compatible"


def test_configuration_merger_resolves_resource_limits_per_field() -> None:
    """Verify one source value never captures absent sibling limit fields."""
    request_limits = InteractionResourceLimits(1, 2, 3)
    integration_limits = InteractionResourceLimits(4, 5, 6)
    client_limits = InteractionResourceLimits(
        max_response_body_bytes=110,
        max_streaming_error_body_bytes=220,
    )
    interaction_limits = InteractionResourceLimits(
        max_response_body_bytes=111,
        max_frame_bytes=333,
    )

    resolved = _merge(
        interaction=InteractionConfigurationLayer(resource_limits=interaction_limits),
        request=InteractionConfigurationLayer(
            target=_target("request"),
            resource_limits=request_limits,
        ),
        client=InteractionConfigurationLayer(resource_limits=client_limits),
        integration=InteractionConfigurationLayer(resource_limits=integration_limits),
    )

    # Winners are interaction, Client, and interaction respectively. Request and
    # integration resource fields are outside the defined source order.
    assert resolved.resource_limits == ResolvedInteractionResourceLimits(
        111,
        220,
        333,
    )


def test_configuration_merger_changes_only_explicit_interaction_fields() -> None:
    """Verify a partial top layer leaves every unrelated lower selection intact."""
    target = _target("request")
    request_access = _access("request")
    client_policy = _policy("permissive")
    client_limits = InteractionResourceLimits(
        max_response_body_bytes=110,
        max_frame_bytes=330,
    )
    interaction_access = _access("interaction")

    baseline = _merge(
        request=InteractionConfigurationLayer(
            target=target,
            service_access=request_access,
        ),
        client=InteractionConfigurationLayer(
            compatibility_policy=client_policy,
            resource_limits=client_limits,
        ),
    )
    overridden = _merge(
        interaction=InteractionConfigurationLayer(service_access=interaction_access),
        request=InteractionConfigurationLayer(
            target=target,
            service_access=request_access,
        ),
        client=InteractionConfigurationLayer(
            compatibility_policy=client_policy,
            resource_limits=client_limits,
        ),
    )

    # Only access differs. The partial layer cannot replace target, policy, limit
    # siblings, or cancellation merely because the layer itself is present.
    assert baseline.service_access is request_access
    assert overridden.service_access is interaction_access
    assert overridden.target is baseline.target
    assert overridden.compatibility_policy is baseline.compatibility_policy
    assert overridden.resource_limits == baseline.resource_limits
    assert overridden.cancellation_signal is baseline.cancellation_signal is None


def test_configuration_merger_scopes_cancellation_to_interaction() -> None:
    """Verify reusable and request/integration signals cannot enter the result."""
    request_signal = _Signal("request")
    client_signal = _Signal("client")
    integration_signal = _Signal("integration")
    interaction_signal = _Signal("interaction")
    request = InteractionConfigurationLayer(
        target=_target("request"),
        cancellation_signal=request_signal,
    )
    client = InteractionConfigurationLayer(cancellation_signal=client_signal)
    integration = InteractionConfigurationLayer(cancellation_signal=integration_signal)

    absent = _merge(request=request, client=client, integration=integration)
    present = _merge(
        interaction=InteractionConfigurationLayer(
            cancellation_signal=interaction_signal
        ),
        request=request,
        client=client,
        integration=integration,
    )

    # Only current-interaction ownership is valid. The merger stores the winning
    # signal by identity and performs no state read or callback subscription.
    assert absent.cancellation_signal is None
    assert present.cancellation_signal is interaction_signal


def test_configuration_merger_preserves_sources_and_selected_references() -> None:
    """Verify merging neither mutates layers nor copies structural selected values."""
    target = _target("request")
    access = _access("client")
    policy = _policy("strict")
    signal = _Signal("interaction")
    interaction = InteractionConfigurationLayer(
        compatibility_policy=policy,
        cancellation_signal=signal,
    )
    request = InteractionConfigurationLayer(target=target)
    client = InteractionConfigurationLayer(service_access=access)

    resolved = _merge(
        interaction=interaction,
        request=request,
        client=client,
    )

    # Identity proves the algorithm selects rather than clones protocol objects;
    # source equality proves defaults were not written back into reusable layers.
    assert resolved.target is target
    assert resolved.service_access is access
    assert resolved.compatibility_policy is policy
    assert resolved.cancellation_signal is signal
    assert interaction == InteractionConfigurationLayer(
        compatibility_policy=policy,
        cancellation_signal=signal,
    )
    assert request == InteractionConfigurationLayer(target=target)
    assert client == InteractionConfigurationLayer(service_access=access)


def test_configuration_merger_validates_overridden_resource_layers() -> None:
    """Verify precedence cannot hide invalid applicable Client configuration."""
    interaction_limits = InteractionResourceLimits(max_response_body_bytes=111)
    client_limits = InteractionResourceLimits(max_response_body_bytes=0)

    # Every applicable explicit layer is validated before selection, so a valid
    # interaction override cannot conceal an invalid reusable Client default.
    _assert_raises(
        ValueError,
        lambda: _merge(
            interaction=InteractionConfigurationLayer(
                resource_limits=interaction_limits
            ),
            request=InteractionConfigurationLayer(target=_target("request")),
            client=InteractionConfigurationLayer(resource_limits=client_limits),
        ),
        "max_response_body_bytes must be positive",
    )


def test_configuration_merger_rejects_invalid_sdk_resource_limit_type() -> None:
    """Verify SDK fallback input must be a complete resolved limit object."""
    unresolved = InteractionResourceLimits(100, 200, 300)

    # The merger delegates to the shared resolver, which keeps unresolved
    # override layers distinct from the mandatory complete SDK fallback tier.
    _assert_raises(
        TypeError,
        lambda: _merge(
            request=InteractionConfigurationLayer(target=_target("request")),
            sdk_limits=cast(ResolvedInteractionResourceLimits, unresolved),
        ),
        "sdk_defaults must be ResolvedInteractionResourceLimits",
    )


def test_configuration_merger_rejects_invalid_source_layer_types() -> None:
    """Verify each named input rejects a dynamically supplied non-layer object."""
    empty = InteractionConfigurationLayer()
    request = InteractionConfigurationLayer(target=_target("request"))
    invalid_calls = (
        (
            lambda: merge_interaction_configuration(
                interaction_layer=cast(InteractionConfigurationLayer, object()),
                request_layer=request,
                client_layer=empty,
                integration_layer=empty,
                sdk_resource_limits=_SDK_LIMITS,
            ),
            "interaction_layer must be InteractionConfigurationLayer",
        ),
        (
            lambda: merge_interaction_configuration(
                interaction_layer=empty,
                request_layer=cast(InteractionConfigurationLayer, object()),
                client_layer=empty,
                integration_layer=empty,
                sdk_resource_limits=_SDK_LIMITS,
            ),
            "request_layer must be InteractionConfigurationLayer",
        ),
        (
            lambda: merge_interaction_configuration(
                interaction_layer=empty,
                request_layer=request,
                client_layer=cast(InteractionConfigurationLayer, object()),
                integration_layer=empty,
                sdk_resource_limits=_SDK_LIMITS,
            ),
            "client_layer must be InteractionConfigurationLayer",
        ),
        (
            lambda: merge_interaction_configuration(
                interaction_layer=empty,
                request_layer=request,
                client_layer=empty,
                integration_layer=cast(InteractionConfigurationLayer, object()),
                sdk_resource_limits=_SDK_LIMITS,
            ),
            "integration_layer must be InteractionConfigurationLayer",
        ),
    )

    # Named diagnostics preserve the precise failed source instead of allowing an
    # arbitrary object to fail later through attribute access.
    for merge_configuration, message in invalid_calls:
        _assert_raises(TypeError, merge_configuration, message)


def test_configuration_merger_remains_internal() -> None:
    """Verify the implementation does not expand the runtime package API."""
    # Direct internal imports support runtime composition while the stable public
    # surface remains unchanged until an architecture step explicitly exposes it.
    assert "merge_interaction_configuration" not in mconet.core.runtime.__all__
