"""Pre-I/O tests for resolved interaction configuration validation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import mconet.core.runtime
from mconet.core.domain import (
    Authorization,
    CancellationSignal,
    CompatibilityPolicy,
    Extensions,
    Headers,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    SecretValue,
    ServiceAccess,
    UriValue,
)
from mconet.core.runtime.resolved_configuration_validation import (
    validate_resolved_configuration,
)
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Per-instance mappings avoid shared mutable test state while satisfying the
    # read-only Extensions protocol exposed by custom domain implementations.
    return {}


def _noop_unsubscribe() -> None:
    """Provide an already-completed remover for the observable signal fixture."""
    # No callback is retained by the fixture, so removal has no state to change.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the nested field diagnostic so failure in another validation phase
    # cannot make a negative configuration test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Custom structural target used by resolved validation tests."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture retaining a protected credential reference."""

    kind: OpenIdentifier
    credential: SecretValue


@dataclass(frozen=True, slots=True)
class _Access:
    """Custom structural service access used by resolved validation tests."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Signal:
    """Structural signal that records property reads and subscription calls."""

    def __init__(self) -> None:
        """Initialize independent observation counters for one test signal."""
        # Separate counters distinguish passive protocol recognition from an
        # actual callback subscription side effect.
        self.property_reads = 0
        self.subscription_calls = 0

    @property
    def is_cancelled(self) -> bool:
        """Record a state observation and return the stable active state."""
        # Increment before returning so every unexpected validation read remains
        # visible even though the boolean state itself never changes.
        self.property_reads += 1
        return False

    @property
    def reason(self) -> str | None:
        """Record a reason observation and return no active cancellation reason."""
        # Reason reads are tracked with state reads because neither belongs to
        # resolved configuration semantic validation.
        self.property_reads += 1
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Record subscription and return a completed idempotent remover."""
        # The callback is deliberately not retained or invoked; this fixture only
        # detects whether validation crosses the signal ownership boundary.
        self.subscription_calls += 1
        del callback
        return _noop_unsubscribe


def _target(model: ModelDescriptor | None = None) -> _Target:
    """Create a complete structural target with an optional model replacement."""
    # None selects the ordinary valid model. Invalid tests pass an explicit
    # descriptor so they exercise the shared target/model validator path.
    selected_model = model if model is not None else NamedModel("model-a")
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        selected_model,
    )


def _configuration(
    *,
    target: ModelTarget | None = None,
    access: ServiceAccess | None = None,
    limits: ResolvedInteractionResourceLimits | None = None,
    signal: CancellationSignal | None = None,
) -> ResolvedInteractionConfiguration:
    """Create a resolved configuration while allowing one validation override."""
    # Explicit None checks preserve valid absence for access while factories fill
    # only target and limit values that are mandatory in the resolved carrier.
    selected_target = target if target is not None else _target()
    selected_limits = (
        limits
        if limits is not None
        else ResolvedInteractionResourceLimits(100, 200, 300)
    )
    return ResolvedInteractionConfiguration(
        target=selected_target,
        service_access=access,
        compatibility_policy=CompatibilityPolicy(OpenIdentifier("compatible")),
        resource_limits=selected_limits,
        cancellation_signal=signal,
    )


def test_resolved_configuration_validator_returns_original_valid_object() -> None:
    """Verify a complete valid configuration preserves its immutable identity."""
    access = _Access(endpoint=UriValue("vendor+rpc://models.example.test", True))
    configuration = _configuration(access=access)

    # Validation observes existing values without normalizing endpoint schemes,
    # replacing structural implementations, or allocating another configuration.
    assert validate_resolved_configuration(configuration) is configuration
    assert configuration.service_access is access


def test_resolved_configuration_validator_allows_absent_service_access() -> None:
    """Verify access may remain absent for later integration-level resolution."""
    configuration = _configuration(access=None)

    # None is not an invalid endpoint; it preserves the explicit unresolved state
    # until the selected integration contributes its access defaults.
    assert validate_resolved_configuration(configuration) is configuration
    assert configuration.service_access is None


def test_resolved_configuration_validator_rejects_missing_model() -> None:
    """Verify a structurally present target with no model fails before later work."""
    target = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        cast(ModelDescriptor, None),
    )
    configuration = _configuration(target=target)

    # Runtime protocol membership proves only attribute presence. The unified
    # validator delegates the non-null model contract before access or I/O.
    _assert_raises(
        TypeError,
        lambda: validate_resolved_configuration(configuration),
        "model must implement ModelDescriptor",
    )


def test_resolved_configuration_validator_rejects_missing_model_name() -> None:
    """Verify blank required model names fail through shared descriptor semantics."""
    configuration = _configuration(target=_target(NamedModel("   ")))

    # Whitespace is not a usable model name and must fail before integration or
    # transport selection rather than being guessed from another target field.
    _assert_raises(
        ValueError,
        lambda: validate_resolved_configuration(configuration),
        "name must not be empty or whitespace",
    )


def test_resolved_configuration_validator_rejects_invalid_endpoint() -> None:
    """Verify relative and syntactically invalid endpoints fail before transport."""
    invalid_cases = (
        (
            _Access(endpoint=UriValue("relative/path", False)),
            "absolute URI",
        ),
        (
            _Access(endpoint=UriValue("missing-scheme", True)),
            "valid scheme",
        ),
    )

    # Both endpoint branches are delegated to the existing ServiceAccess
    # validator, preserving its stable field-level diagnostics unchanged.
    for access, message in invalid_cases:
        configuration = _configuration(access=access)
        _assert_raises(
            ValueError,
            lambda configuration=configuration: validate_resolved_configuration(
                configuration
            ),
            message,
        )


def test_resolved_configuration_validator_rejects_every_invalid_limit() -> None:
    """Verify nonpositive and overflowing resolved limits fail independently."""
    invalid_cases = (
        (
            ResolvedInteractionResourceLimits(0, 200, 300),
            "max_response_body_bytes must be positive",
        ),
        (
            ResolvedInteractionResourceLimits(100, -1, 300),
            "max_streaming_error_body_bytes must be positive",
        ),
        (
            ResolvedInteractionResourceLimits(100, 200, 1 << 63),
            "max_frame_bytes must fit signed 64-bit range",
        ),
    )

    # The complete resolved carrier cannot use omission or an unlimited sentinel;
    # every concrete field passes through the same shared Int64/positive checks.
    for limits, message in invalid_cases:
        configuration = _configuration(limits=limits)
        _assert_raises(
            ValueError,
            lambda configuration=configuration: validate_resolved_configuration(
                configuration
            ),
            message,
        )


def test_resolved_configuration_validator_does_not_read_secret() -> None:
    """Verify access validation observes authorization kind but not credential text."""
    secret_text = "placeholder-resolved-validator-secret"
    authorization = _Authorization(
        OpenIdentifier("authorization.vendor"),
        SecretValue(secret_text),
    )
    access = _Access(authorization=authorization)
    configuration = _configuration(access=access)

    validated = validate_resolved_configuration(configuration)

    # The opaque Authorization object and SecretValue remain the original
    # references; validation neither reveals nor copies credential plaintext.
    assert validated.service_access is access
    assert access.authorization is authorization
    assert secret_text not in repr(validated)
    assert "[REDACTED]" in repr(validated)


def test_resolved_configuration_validator_does_not_inspect_cancellation() -> None:
    """Verify semantic validation neither reads nor subscribes to the signal."""
    signal = _Signal()
    configuration = _configuration(signal=signal)
    construction_reads = signal.property_reads
    construction_subscriptions = signal.subscription_calls

    validated = validate_resolved_configuration(configuration)

    # Runtime protocol recognition during configuration construction may inspect
    # properties, so compare post-construction counters rather than assuming zero.
    assert validated.cancellation_signal is signal
    assert signal.property_reads == construction_reads
    assert signal.subscription_calls == construction_subscriptions


def test_resolved_configuration_validator_uses_deterministic_phase_order() -> None:
    """Verify target errors precede simultaneous access and resource failures."""
    configuration = _configuration(
        target=_target(NamedModel("")),
        access=_Access(endpoint=UriValue("relative/path", False)),
        limits=ResolvedInteractionResourceLimits(0, 0, 0),
    )

    # Stable target→access→limits ordering gives callers one deterministic first
    # diagnostic and guarantees no later validation hides the missing model.
    _assert_raises(
        ValueError,
        lambda: validate_resolved_configuration(configuration),
        "name must not be empty or whitespace",
    )


def test_resolved_configuration_validator_rejects_invalid_input_type() -> None:
    """Verify arbitrary field-shaped objects cannot enter the unified boundary."""
    # The nominal carrier has already established complete fields and immutable
    # storage; dynamic callers cannot bypass it with an unrelated object.
    _assert_raises(
        TypeError,
        lambda: validate_resolved_configuration(
            cast(ResolvedInteractionConfiguration, object())
        ),
        "configuration must be ResolvedInteractionConfiguration",
    )


def test_resolved_configuration_validator_remains_internal() -> None:
    """Verify validation composition does not expand the public runtime API."""
    # Runtime orchestration can import the validator directly while public users
    # continue to interact through higher-level APIs introduced in later steps.
    assert "validate_resolved_configuration" not in mconet.core.runtime.__all__
