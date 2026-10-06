"""Redaction and validation tests for safe configuration snapshot mapping."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast

import mconet.core.runtime
from mconet.core.domain import (
    Authorization,
    CancellationSignal,
    CompatibilityPolicy,
    Extensions,
    HeaderField,
    Headers,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    SecretValue,
    ServiceAccess,
    UriValue,
)
from mconet.core.runtime.configuration_snapshot_mapping import (
    map_safe_configuration_snapshot,
)
from mconet.core.runtime.resolved_interaction_configuration import (
    ResolvedInteractionConfiguration,
)
from mconet.core.runtime.safe_configuration_snapshot import (
    SafeConfigurationSnapshot,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SECRET_SCANNER = _PROJECT_ROOT / "scripts" / "check_secrets.py"


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural fixtures."""
    # Per-instance mappings avoid shared mutable test state while preserving the
    # read-only protocol type used by custom target and access implementations.
    return {}


def _noop_unsubscribe() -> None:
    """Provide an already-completed remover for the observable signal fixture."""
    # The fixture never retains a callback, so removal has no state to change.
    return None


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the validation diagnostic so an unrelated mapper failure cannot make
    # a negative precondition test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Custom target fixture with explicit safe and excluded data boundaries."""

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
    """Custom access fixture containing data the Mapper must never copy."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _Signal:
    """Structural signal that records mapper-visible reads and subscriptions."""

    def __init__(self) -> None:
        """Initialize independent observation counters for one signal instance."""
        # Separate property and subscription counters identify the exact kind of
        # ownership-boundary violation if mapping gains an unintended side effect.
        self.property_reads = 0
        self.subscription_calls = 0

    @property
    def is_cancelled(self) -> bool:
        """Record one state read and report a stable active signal."""
        # Increment before return so even a discarded mapper observation is visible.
        self.property_reads += 1
        return False

    @property
    def reason(self) -> str | None:
        """Record one reason read and return no active cancellation reason."""
        # The mapper needs only signal presence, so any reason access is a failure.
        self.property_reads += 1
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Record subscription and return a completed idempotent remover."""
        # Do not retain or invoke the callback; the counter alone detects whether
        # snapshot mapping accidentally starts observing cancellation lifecycle.
        self.subscription_calls += 1
        del callback
        return _noop_unsubscribe


def _target(
    *,
    model: ModelDescriptor | None = None,
    deployment_id: str | None = "deployment-a",
    extensions: Extensions | None = None,
) -> _Target:
    """Create one structural target with optional validation/redaction inputs."""
    # Explicit None selects safe defaults, while supplied values let each test
    # introduce one controlled semantic or redaction condition.
    selected_model = model if model is not None else NamedModel("model-a")
    selected_extensions: Extensions = extensions if extensions is not None else {}
    return _Target(
        service_id=OpenIdentifier("service.vendor"),
        protocol_id=OpenIdentifier("protocol.vendor"),
        model=selected_model,
        deployment_id=deployment_id,
        extensions=selected_extensions,
    )


def _configuration(
    *,
    target: ModelTarget | None = None,
    access: ServiceAccess | None = None,
    limits: ResolvedInteractionResourceLimits | None = None,
    signal: CancellationSignal | None = None,
    policy: CompatibilityPolicy | None = None,
) -> ResolvedInteractionConfiguration:
    """Create complete resolved configuration with typed per-field overrides."""
    # Explicit None checks preserve valid absence for optional access/signal while
    # factories fill only fields required by the resolved configuration carrier.
    selected_target = target if target is not None else _target()
    selected_limits = (
        limits
        if limits is not None
        else ResolvedInteractionResourceLimits(100, 200, 300)
    )
    selected_policy = (
        policy
        if policy is not None
        else CompatibilityPolicy(OpenIdentifier("compatible"))
    )
    return ResolvedInteractionConfiguration(
        target=selected_target,
        service_access=access,
        compatibility_policy=selected_policy,
        resource_limits=selected_limits,
        cancellation_signal=signal,
    )


def test_configuration_snapshot_mapper_copies_only_approved_scalar_facts() -> None:
    """Verify every safe source field maps exactly to the closed snapshot shape."""
    target = _target(
        model=NamedModel("model-safe"),
        deployment_id="deployment-safe",
    )
    access = _Access(endpoint=UriValue("https://models.example.test", True))
    signal = _Signal()
    configuration = _configuration(
        target=target,
        access=access,
        limits=ResolvedInteractionResourceLimits(111, 222, 333),
        signal=signal,
        policy=CompatibilityPolicy(OpenIdentifier("strict")),
    )

    snapshot = map_safe_configuration_snapshot(configuration)

    # Every value is a plain immutable JSON leaf and no target/access object is
    # retained by reference in the snapshot.
    assert snapshot == SafeConfigurationSnapshot(
        service_id="service.vendor",
        protocol_id="protocol.vendor",
        model_name="model-safe",
        deployment_id="deployment-safe",
        service_access_configured=True,
        compatibility_policy="strict",
        max_response_body_bytes=111,
        max_streaming_error_body_bytes=222,
        max_frame_bytes=333,
        cancellation_configured=True,
    )


def test_configuration_snapshot_mapper_preserves_explicit_absence() -> None:
    """Verify optional deployment, access, and cancellation map without sentinels."""
    configuration = _configuration(target=_target(deployment_id=None))

    snapshot = map_safe_configuration_snapshot(configuration)

    # None is reserved for absent deployment; separate booleans preserve access
    # and cancellation absence without copying either source object.
    assert snapshot.deployment_id is None
    assert snapshot.service_access_configured is False
    assert snapshot.cancellation_configured is False


def test_configuration_snapshot_mapper_validates_before_mapping() -> None:
    """Verify invalid model, endpoint, and limit inputs fail with shared diagnostics."""
    invalid_cases = (
        (
            _configuration(target=_target(model=NamedModel(""))),
            "name must not be empty or whitespace",
        ),
        (
            _configuration(access=_Access(endpoint=UriValue("relative/path", False))),
            "endpoint must be an absolute URI",
        ),
        (
            _configuration(limits=ResolvedInteractionResourceLimits(0, 200, 300)),
            "max_response_body_bytes must be positive",
        ),
    )

    # Mapper preconditions are the unified Validator contract; it does not create
    # a partially populated snapshot and validate after sensitive traversal.
    for configuration, message in invalid_cases:
        _assert_raises(
            ValueError,
            lambda configuration=configuration: map_safe_configuration_snapshot(
                configuration
            ),
            message,
        )


def test_configuration_snapshot_mapper_omits_sensitive_and_arbitrary_payloads(
    tmp_path: Path,
) -> None:
    """Verify a canary in every excluded source remains absent and scans clean."""
    canary = "sk-" + ("A" * 32)
    credential_url = "https://" + "user:" + canary + "@models.example.test"
    authorization = _Authorization(
        OpenIdentifier("authorization.vendor"),
        SecretValue(canary),
    )
    access = _Access(
        endpoint=UriValue(credential_url, True),
        authorization=authorization,
        headers=Headers((HeaderField("X-Api-Key", canary),)),
        query=QueryParameters((QueryParameter("api_key", canary),)),
        api_version=canary,
        project_id=canary,
        tenant_id=canary,
        extensions={"secret": canary},
    )
    model = NamedModel(
        "model-safe",
        display_name=canary,
        description=canary,
        metadata={"secret": canary},
        extensions={"secret": canary},
    )
    configuration = _configuration(
        target=_target(model=model, extensions={"secret": canary}),
        access=access,
    )

    snapshot = map_safe_configuration_snapshot(configuration)
    encoded = json.dumps(asdict(snapshot), sort_keys=True)
    fixture = tmp_path / "configuration-snapshot.json"
    fixture.write_text(encoded, encoding="utf-8")
    scan = subprocess.run(
        [sys.executable, str(_SECRET_SCANNER), str(fixture)],
        check=False,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # The provider-shaped canary would be detected if any model metadata, access
    # field, Authorization credential, or custom extension entered the snapshot.
    assert canary not in encoded
    assert credential_url not in encoded
    assert set(asdict(snapshot)) == {
        "service_id",
        "protocol_id",
        "model_name",
        "deployment_id",
        "service_access_configured",
        "compatibility_policy",
        "max_response_body_bytes",
        "max_streaming_error_body_bytes",
        "max_frame_bytes",
        "cancellation_configured",
    }
    assert scan.returncode == 0, scan.stdout + scan.stderr


def test_configuration_snapshot_mapper_does_not_inspect_cancellation() -> None:
    """Verify mapping records signal presence without reading or subscribing."""
    signal = _Signal()
    configuration = _configuration(signal=signal)
    construction_reads = signal.property_reads
    construction_subscriptions = signal.subscription_calls

    snapshot = map_safe_configuration_snapshot(configuration)

    # Protocol recognition during configuration construction may inspect fields;
    # validation and mapping must add no reads or subscriptions beyond that baseline.
    assert snapshot.cancellation_configured is True
    assert signal.property_reads == construction_reads
    assert signal.subscription_calls == construction_subscriptions


def test_configuration_snapshot_mapper_does_not_mutate_source() -> None:
    """Verify mapping creates a new snapshot without changing resolved input."""
    target = _target()
    access = _Access()
    configuration = _configuration(target=target, access=access)

    first = map_safe_configuration_snapshot(configuration)
    second = map_safe_configuration_snapshot(configuration)

    # Deterministic equal snapshots are separate immutable values, while all
    # structural source references remain exactly as supplied by the caller.
    assert first == second
    assert first is not second
    assert configuration.target is target
    assert configuration.service_access is access


def test_configuration_snapshot_mapper_rejects_invalid_input_type() -> None:
    """Verify arbitrary objects fail through the unified validation boundary."""
    # The Mapper performs no field access before validation, so a dynamic invalid
    # input receives the stable resolved-configuration diagnostic.
    _assert_raises(
        TypeError,
        lambda: map_safe_configuration_snapshot(
            cast(ResolvedInteractionConfiguration, object())
        ),
        "configuration must be ResolvedInteractionConfiguration",
    )


def test_configuration_snapshot_mapper_remains_internal() -> None:
    """Verify snapshot mapping does not expand the public runtime API."""
    # Direct internal imports support later monitoring orchestration while the
    # stable consumer-facing surface remains unchanged.
    assert "map_safe_configuration_snapshot" not in mconet.core.runtime.__all__
