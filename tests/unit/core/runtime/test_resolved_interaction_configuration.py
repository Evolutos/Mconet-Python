"""Completeness and safety tests for ResolvedInteractionConfiguration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, field, fields
from inspect import Parameter, signature
from typing import cast

import mconet.core.domain
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
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
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
    # Separate mappings prevent test fixtures from sharing mutable implementation
    # state while their public annotations remain read-only.
    return {}


def _noop_unsubscribe() -> None:
    """Provide an already-completed remover for the passive signal fixture."""
    # The fixture retains no callback, so removal has no state to change.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the field diagnostic so a failure in another resolved dimension
    # cannot make a negative storage test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Custom structural target used by resolved configuration tests."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture retaining a protected SecretValue reference."""

    kind: OpenIdentifier
    credential: SecretValue


@dataclass(frozen=True, slots=True)
class _Access:
    """Custom access fixture that may own opaque authorization state."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Signal:
    """Passive structural cancellation signal retained by reference."""

    @property
    def is_cancelled(self) -> bool:
        """Return the fixture's stable active state."""
        # Configuration construction must not turn storage into cancellation.
        return False

    @property
    def reason(self) -> str | None:
        """Return no reason while the fixture remains active."""
        # The separate state property distinguishes activity from no-reason cancel.
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Return a completed remover without retaining the callback."""
        # This passive fixture has no source and proves construction does not
        # subscribe as a side effect.
        del callback
        return _noop_unsubscribe


def _target() -> _Target:
    """Create one complete custom target for resolved configuration tests."""
    # A factory keeps each test independent while using stable portable IDs.
    return _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("model-a"),
    )


def _policy() -> CompatibilityPolicy:
    """Create the concrete compatible policy used by valid fixtures."""
    # Construct through the public value path instead of a test-only sentinel.
    return CompatibilityPolicy(OpenIdentifier("compatible"))


def _limits() -> ResolvedInteractionResourceLimits:
    """Create complete finite limits used by valid configuration fixtures."""
    # Distinct values make field transposition visible in assertion failures.
    return ResolvedInteractionResourceLimits(100, 200, 300)


def test_resolved_interaction_configuration_requires_every_field() -> None:
    """Verify the constructor exposes all five fields without hidden defaults."""
    constructor_parameters = signature(ResolvedInteractionConfiguration).parameters

    # Even optional-valued access and cancellation fields are explicit resolved
    # states, so callers cannot accidentally omit one from the snapshot shape.
    assert tuple(constructor_parameters) == _EXPECTED_FIELDS
    for field_name in _EXPECTED_FIELDS:
        assert constructor_parameters[field_name].default is Parameter.empty


def test_resolved_interaction_configuration_stores_complete_input() -> None:
    """Verify each selected value retains its original reference and meaning."""
    target = _target()
    access = _Access(endpoint=UriValue("https://example.test", True))
    policy = _policy()
    limits = _limits()
    signal = _Signal()

    configuration = ResolvedInteractionConfiguration(
        target,
        access,
        policy,
        limits,
        signal,
    )

    # The resolved carrier neither normalizes nor copies selected objects; later
    # validators and resolvers consume the exact immutable selection result.
    assert configuration.target is target
    assert configuration.service_access is access
    assert configuration.compatibility_policy is policy
    assert configuration.resource_limits is limits
    assert configuration.cancellation_signal is signal


def test_resolved_interaction_configuration_preserves_explicit_absence() -> None:
    """Verify access and cancellation may be explicitly absent after merging."""
    configuration = ResolvedInteractionConfiguration(
        _target(),
        None,
        _policy(),
        _limits(),
        None,
    )

    # Access None allows the selected integration to contribute a later default;
    # cancellation None means this interaction has no caller-owned signal.
    assert configuration.service_access is None
    assert configuration.cancellation_signal is None


def test_resolved_interaction_configuration_has_exact_internal_shape() -> None:
    """Verify no components, monitors, or secret snapshot fields are present."""
    field_names = tuple(
        field.name for field in fields(ResolvedInteractionConfiguration)
    )

    # An exact field set prevents behavior objects and duplicated secret material
    # from silently becoming part of the immutable configuration result.
    assert field_names == _EXPECTED_FIELDS
    assert "ResolvedInteractionConfiguration" not in mconet.core.runtime.__all__
    assert "ResolvedInteractionConfiguration" not in mconet.core.domain.__all__


def test_resolved_interaction_configuration_does_not_snapshot_secret() -> None:
    """Verify authorization remains an opaque reference without plaintext copying."""
    secret_text = "placeholder-resolved-config-secret"
    authorization = _Authorization(
        OpenIdentifier("authorization.vendor"),
        SecretValue(secret_text),
    )
    access = _Access(authorization=authorization)

    configuration = ResolvedInteractionConfiguration(
        _target(),
        access,
        _policy(),
        _limits(),
        None,
    )

    # The configuration retains only the access object. SecretValue controls the
    # credential, and ordinary configuration representation cannot expose text.
    assert configuration.service_access is access
    assert access.authorization is authorization
    assert secret_text not in repr(configuration)
    assert "[REDACTED]" in repr(configuration)


def test_resolved_interaction_configuration_defers_semantic_validation() -> None:
    """Verify nominally complete but invalid values remain available to Validator."""
    invalid_limits = ResolvedInteractionResourceLimits(0, 200, 300)

    configuration = ResolvedInteractionConfiguration(
        _target(),
        None,
        _policy(),
        invalid_limits,
        None,
    )

    # This type guarantees storage completeness only. A dedicated later validator
    # owns model, endpoint, and resource-limit semantic diagnostics.
    assert configuration.resource_limits is invalid_limits
    assert configuration.resource_limits.max_response_body_bytes == 0


def test_resolved_interaction_configuration_is_immutable() -> None:
    """Verify selected fields cannot be replaced after resolution."""
    configuration = ResolvedInteractionConfiguration(
        _target(),
        None,
        _policy(),
        _limits(),
        None,
    )

    # Frozen storage ensures concurrent consumers observe one stable selection
    # and cannot write values back into shared Client configuration.
    _assert_raises(
        FrozenInstanceError,
        lambda: configuration.__setattr__("compatibility_policy", _policy()),
        "cannot assign to field",
    )


def test_resolved_interaction_configuration_rejects_invalid_field_types() -> None:
    """Verify every field enforces its complete nominal storage boundary."""
    invalid_configurations = (
        (
            lambda: ResolvedInteractionConfiguration(
                cast(ModelTarget, object()), None, _policy(), _limits(), None
            ),
            "target must implement ModelTarget",
        ),
        (
            lambda: ResolvedInteractionConfiguration(
                _target(), cast(ServiceAccess, object()), _policy(), _limits(), None
            ),
            "service_access must implement ServiceAccess",
        ),
        (
            lambda: ResolvedInteractionConfiguration(
                _target(),
                None,
                cast(CompatibilityPolicy, object()),
                _limits(),
                None,
            ),
            "compatibility_policy must be CompatibilityPolicy",
        ),
        (
            lambda: ResolvedInteractionConfiguration(
                _target(),
                None,
                _policy(),
                cast(ResolvedInteractionResourceLimits, object()),
                None,
            ),
            "resource_limits must be ResolvedInteractionResourceLimits",
        ),
        (
            lambda: ResolvedInteractionConfiguration(
                _target(),
                None,
                _policy(),
                _limits(),
                cast(CancellationSignal, object()),
            ),
            "cancellation_signal must implement CancellationSignal",
        ),
    )

    # Failures identify the exact selected dimension before any downstream
    # validator or resolver could encounter an unrelated attribute error.
    for create_configuration, message in invalid_configurations:
        _assert_raises(TypeError, create_configuration, message)
