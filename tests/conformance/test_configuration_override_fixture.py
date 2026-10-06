"""Conformance checks for language-neutral configuration override fixtures."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast

from mconet.core.domain import (
    Authorization,
    CompatibilityPolicy,
    Extensions,
    Headers,
    InteractionResourceLimits,
    JsonValue,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    ResolvedInteractionResourceLimits,
    UriValue,
)
from mconet.core.runtime.configuration_snapshot_mapping import (
    map_safe_configuration_snapshot,
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
from mconet.testing import json_fixtures_equal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _PROJECT_ROOT
    / "spec"
    / "fixtures"
    / "r1-text-unary"
    / "configuration-overrides.json"
)
_INDEX_PATH = _FIXTURE_PATH.parent / "index.json"
_PRECEDENCE_PATH = _FIXTURE_PATH.parent / "configuration-precedence.json"
_SOURCE_NAMES = ("interaction", "request", "client", "integration")
_RESOURCE_FIELDS = (
    "maxResponseBodyBytes",
    "maxStreamingErrorBodyBytes",
    "maxFrameBytes",
)
_RESOURCE_ATTRIBUTES = {
    "maxResponseBodyBytes": "max_response_body_bytes",
    "maxStreamingErrorBodyBytes": "max_streaming_error_body_bytes",
    "maxFrameBytes": "max_frame_bytes",
}
_EMPTY_EXTENSIONS: Extensions = {}


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for structural Fixture values."""
    # Each protocol implementation receives a fresh mapping so no Case can
    # mutate shared test state through a concrete dictionary reference.
    return dict(_EMPTY_EXTENSIONS)


def _noop_unsubscribe() -> None:
    """Return from removal of a passive Fixture signal subscription."""
    # No callback is retained, so the remover has no state transition to apply.
    return None


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target whose marker identifies its configuration source."""

    marker: str
    """Language-neutral source name used only by conformance observation."""

    service_id: OpenIdentifier
    """Valid source-specific service identifier."""

    protocol_id: OpenIdentifier
    """Valid source-specific protocol identifier."""

    model: ModelDescriptor
    """Valid source-specific model descriptor."""

    deployment_id: str | None
    """Source-specific deployment identifier included in safe snapshots."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Empty target extension mapping for precedence-only Cases."""


@dataclass(frozen=True, slots=True)
class _Access:
    """Structural non-sensitive access value carrying one source marker."""

    marker: str
    """Language-neutral source name used only by conformance observation."""

    endpoint: UriValue | None
    """Valid source-specific absolute endpoint."""

    authorization: Authorization | None = None
    """Authorization stays absent from ordinary configuration Fixtures."""

    headers: Headers = field(default_factory=Headers)
    """Empty non-sensitive Header context."""

    query: QueryParameters = field(default_factory=QueryParameters)
    """Empty non-sensitive Query context."""

    api_version: str | None = None
    """Optional API version, unused by source-selection Cases."""

    project_id: str | None = None
    """Optional project context, unused by source-selection Cases."""

    tenant_id: str | None = None
    """Optional tenant context, unused by source-selection Cases."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Empty access extension mapping for precedence-only Cases."""


@dataclass(frozen=True, slots=True)
class _Signal:
    """Passive cancellation signal whose marker identifies its source."""

    marker: str
    """Language-neutral source name retained without state inspection."""

    @property
    def is_cancelled(self) -> bool:
        """Report the stable active state of the passive Fixture signal."""
        # Configuration merge and snapshot mapping need only signal presence and
        # must not cause a cancellation transition.
        return False

    @property
    def reason(self) -> str | None:
        """Return no reason while the passive Fixture signal remains active."""
        # None represents absence of a cancellation reason, not a source marker.
        return None

    def subscribe(
        self,
        callback: Callable[[str | None], None],
    ) -> Callable[[], None]:
        """Return a completed remover without retaining the callback."""
        # The Fixture exercises reference selection only, so subscription would
        # introduce unrelated lifecycle behavior and is explicitly discarded.
        del callback
        return _noop_unsubscribe


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    # Object envelopes provide stable named fields across language decoders and
    # prevent a malformed array root from acquiring positional semantics.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued Fixture field."""
    # Reject missing and scalar values before decoding nested configuration so
    # casts cannot conceal a malformed language-neutral Case.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued Fixture field."""
    # Case ordering remains explicit and duplicates stay visible instead of being
    # overwritten as they would be in a name-keyed object.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string without host-language coercion."""
    # Source markers and modes are contract text; numbers, booleans, or null must
    # not be converted into platform-specific spellings.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string while rejecting other JSON kinds."""
    # Expected observations use null for true absence and never a textual
    # sentinel, preserving the same distinction as resolved configuration.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _require_integer(value: JsonValue | None, field_name: str) -> int:
    """Return one exact JSON integer and reject booleans or floating point."""
    # Python bool is an int subclass, so exact type membership is required to
    # preserve the language-neutral numeric contract for byte limits.
    if type(value) is not int:
        raise AssertionError(f"{field_name} must be a JSON integer.")
    return value


def _target(marker: str) -> _Target:
    """Create a valid target whose safe scalar fields expose its source marker."""
    # Dot-separated identifiers and opaque model/deployment names allow Snapshot
    # assertions to prove which complete target reference won precedence.
    return _Target(
        marker=marker,
        service_id=OpenIdentifier(f"service.{marker}"),
        protocol_id=OpenIdentifier(f"protocol.{marker}"),
        model=NamedModel(f"model-{marker}"),
        deployment_id=f"deployment-{marker}",
    )


def _access(marker: str) -> _Access:
    """Create valid non-sensitive access whose endpoint exposes its source marker."""
    # Authorization remains absent; a stable HTTPS authority makes the object
    # independently valid before it enters resolved configuration validation.
    return _Access(
        marker=marker,
        endpoint=UriValue(f"https://{marker}.example.test", True),
    )


def _resource_limits(
    document: dict[str, JsonValue],
    field_name: str,
) -> InteractionResourceLimits:
    """Decode one optional per-field resource-limit source object."""
    # Each field is decoded independently so absence falls through without
    # promoting sibling values from the same layer.
    values: dict[str, int | None] = {}
    for fixture_name, attribute_name in _RESOURCE_ATTRIBUTES.items():
        raw_value = document.get(fixture_name)
        values[attribute_name] = (
            _require_integer(raw_value, f"{field_name}.{fixture_name}")
            if raw_value is not None
            else None
        )
    return InteractionResourceLimits(**values)


def _resolved_resource_limits(
    document: dict[str, JsonValue],
    field_name: str,
) -> ResolvedInteractionResourceLimits:
    """Decode the complete SDK safe-default resource-limit object."""
    # SDK defaults cannot contain absence; all three positive fields are required
    # before the production resolver is invoked.
    return ResolvedInteractionResourceLimits(
        max_response_body_bytes=_require_integer(
            document.get("maxResponseBodyBytes"),
            f"{field_name}.maxResponseBodyBytes",
        ),
        max_streaming_error_body_bytes=_require_integer(
            document.get("maxStreamingErrorBodyBytes"),
            f"{field_name}.maxStreamingErrorBodyBytes",
        ),
        max_frame_bytes=_require_integer(
            document.get("maxFrameBytes"),
            f"{field_name}.maxFrameBytes",
        ),
    )


def _decode_layer(
    document: dict[str, JsonValue],
    source_name: str,
) -> InteractionConfigurationLayer:
    """Decode one symbolic source into the internal immutable layer carrier."""
    target_marker = _optional_string(document.get("target"), "target")
    access_marker = _optional_string(document.get("serviceAccess"), "serviceAccess")
    policy_value = _optional_string(
        document.get("compatibilityPolicy"), "compatibilityPolicy"
    )
    signal_marker = _optional_string(
        document.get("cancellationSignal"), "cancellationSignal"
    )
    limits_value = document.get("resourceLimits")

    # Markers must identify their containing source so expected selected-source
    # diagnostics cannot be forged by placing a differently named object in it.
    for field_name, marker in (
        ("target", target_marker),
        ("serviceAccess", access_marker),
        ("cancellationSignal", signal_marker),
    ):
        if marker is not None and marker != source_name:
            raise AssertionError(f"{field_name} marker must match {source_name}.")

    return InteractionConfigurationLayer(
        target=_target(target_marker) if target_marker is not None else None,
        service_access=_access(access_marker) if access_marker is not None else None,
        compatibility_policy=(
            CompatibilityPolicy(OpenIdentifier(policy_value))
            if policy_value is not None
            else None
        ),
        resource_limits=(
            _resource_limits(
                _require_object(limits_value, "resourceLimits"),
                "resourceLimits",
            )
            if limits_value is not None
            else None
        ),
        cancellation_signal=(
            _Signal(signal_marker) if signal_marker is not None else None
        ),
    )


def _decode_sources(
    document: dict[str, JsonValue],
) -> dict[str, InteractionConfigurationLayer]:
    """Decode all four required source objects for one configuration Case."""
    layers: dict[str, InteractionConfigurationLayer] = {}
    for source_name in _SOURCE_NAMES:
        source = _require_object(document.get(source_name), f"sources.{source_name}")
        layers[source_name] = _decode_layer(source, source_name)
    return layers


def _merge_case(
    layers: dict[str, InteractionConfigurationLayer],
    sdk_limits: ResolvedInteractionResourceLimits,
) -> ResolvedInteractionConfiguration:
    """Run the production merger with explicitly named decoded sources."""
    # Explicit keys keep source transposition visible and mirror the production
    # call boundary instead of relying on dictionary iteration order.
    return merge_interaction_configuration(
        interaction_layer=layers["interaction"],
        request_layer=layers["request"],
        client_layer=layers["client"],
        integration_layer=layers["integration"],
        sdk_resource_limits=sdk_limits,
    )


def _reference_source(
    selected: object | None,
    layers: dict[str, InteractionConfigurationLayer],
    attribute_name: str,
    source_order: tuple[str, ...],
    *,
    allow_unmatched: bool = False,
) -> str | None:
    """Identify a selected object by identity among its applicable sources.

    Args:
        selected: Resolved object reference, or None when the result is absent.
        layers: Decoded configuration sources keyed by language-neutral name.
        attribute_name: Layer attribute whose references are candidates.
        source_order: Applicable source names in precedence order.
        allow_unmatched: Whether a non-layer SDK-created default may return None.

    Returns:
        The unique matching source, or None for absence/an allowed SDK default.

    Raises:
        AssertionError: If provenance is missing or ambiguous when not allowed.
    """
    if selected is None:
        return None
    matches = [
        source_name
        for source_name in source_order
        if selected is getattr(layers[source_name], attribute_name)
    ]
    # Identity prevents equal values from obscuring the actual source reference
    # selected by the production merger.
    if not matches and allow_unmatched:
        # CompatibilityPolicy is the only current reference field whose SDK
        # fallback is constructed by the merger instead of stored in a layer.
        return None
    if len(matches) != 1:
        raise AssertionError(f"Could not identify source for {attribute_name}.")
    return matches[0]


def _resource_source(
    value: int,
    layers: dict[str, InteractionConfigurationLayer],
    sdk_limits: ResolvedInteractionResourceLimits,
    attribute_name: str,
) -> str:
    """Identify one resolved integer from unique applicable source values."""
    candidates: list[tuple[str, int]] = []
    for source_name in ("interaction", "client"):
        limits = layers[source_name].resource_limits
        if limits is not None:
            candidate = getattr(limits, attribute_name)
            if candidate is not None:
                candidates.append((source_name, candidate))
    candidates.append(("sdk_safe_default", getattr(sdk_limits, attribute_name)))
    matches = [
        source_name for source_name, candidate in candidates if candidate == value
    ]

    # Fixture values are intentionally unique across applicable sources so an
    # equality match proves provenance rather than merely coincident value.
    if len(matches) != 1:
        raise AssertionError(f"Could not uniquely identify {attribute_name} source.")
    return matches[0]


def _resolved_observation(
    resolved: ResolvedInteractionConfiguration,
) -> dict[str, JsonValue]:
    """Map resolved configuration into the Fixture's non-sensitive result shape."""
    if not isinstance(resolved.target, _Target):
        raise AssertionError("Resolved target must be a Fixture target.")
    access = resolved.service_access
    if access is not None and not isinstance(access, _Access):
        raise AssertionError("Resolved access must be a Fixture access.")
    signal = resolved.cancellation_signal
    if signal is not None and not isinstance(signal, _Signal):
        raise AssertionError("Resolved signal must be a Fixture signal.")

    # Marker extraction observes only test-owned source labels and never endpoint,
    # Authorization, extension, or cancellation state payloads.
    return {
        "target": resolved.target.marker,
        "serviceAccess": access.marker if access is not None else None,
        "compatibilityPolicy": resolved.compatibility_policy.mode.value,
        "resourceLimits": {
            "maxResponseBodyBytes": resolved.resource_limits.max_response_body_bytes,
            "maxStreamingErrorBodyBytes": (
                resolved.resource_limits.max_streaming_error_body_bytes
            ),
            "maxFrameBytes": resolved.resource_limits.max_frame_bytes,
        },
        "cancellationSignal": signal.marker if signal is not None else None,
    }


def _selected_sources(
    resolved: ResolvedInteractionConfiguration,
    layers: dict[str, InteractionConfigurationLayer],
    sdk_limits: ResolvedInteractionResourceLimits,
) -> dict[str, JsonValue]:
    """Map actual selected references and limit values to source names."""
    limits = resolved.resource_limits
    # Each field uses its own provenance lookup so a partial interaction layer
    # cannot incorrectly label sibling fields resolved from lower priorities.
    return {
        "target": _reference_source(
            resolved.target, layers, "target", ("request", "client")
        ),
        "serviceAccess": _reference_source(
            resolved.service_access,
            layers,
            "service_access",
            ("interaction", "request", "client", "integration"),
        ),
        "compatibilityPolicy": (
            _reference_source(
                resolved.compatibility_policy,
                layers,
                "compatibility_policy",
                ("interaction", "client"),
                allow_unmatched=True,
            )
            or "sdk_safe_default"
        ),
        "resourceLimits": {
            fixture_name: _resource_source(
                getattr(limits, attribute_name),
                layers,
                sdk_limits,
                attribute_name,
            )
            for fixture_name, attribute_name in _RESOURCE_ATTRIBUTES.items()
        },
        "cancellationSignal": _reference_source(
            resolved.cancellation_signal,
            layers,
            "cancellation_signal",
            ("interaction",),
        ),
    }


def _snapshot_observation(
    resolved: ResolvedInteractionConfiguration,
) -> dict[str, JsonValue]:
    """Map the production safe snapshot to language-neutral Fixture field names."""
    snapshot = map_safe_configuration_snapshot(resolved)
    raw = asdict(snapshot)

    # The explicit mapping is a compatibility boundary: Python attribute naming
    # cannot leak into a Fixture shared by languages with different conventions.
    return {
        "serviceId": cast(str, raw["service_id"]),
        "protocolId": cast(str, raw["protocol_id"]),
        "modelName": cast(str, raw["model_name"]),
        "deploymentId": cast(str | None, raw["deployment_id"]),
        "serviceAccessConfigured": cast(bool, raw["service_access_configured"]),
        "compatibilityPolicy": cast(str, raw["compatibility_policy"]),
        "maxResponseBodyBytes": cast(int, raw["max_response_body_bytes"]),
        "maxStreamingErrorBodyBytes": cast(int, raw["max_streaming_error_body_bytes"]),
        "maxFrameBytes": cast(int, raw["max_frame_bytes"]),
        "cancellationConfigured": cast(bool, raw["cancellation_configured"]),
    }


def test_configuration_override_fixture_is_registered_and_linked() -> None:
    """Verify discovery, format, precedence linkage, and case-name uniqueness."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)
    resources = _require_array(index.get("resources"), "resources")
    cases = _require_array(fixture.get("cases"), "cases")

    # The executable Cases explicitly depend on the separately reviewed priority
    # resource instead of duplicating or silently replacing its rules.
    assert "configuration-overrides.json" in resources
    assert frozenset(fixture) == frozenset(
        {"format_version", "precedenceResource", "sdkResourceLimits", "cases"}
    )
    assert fixture["format_version"] == 1
    assert fixture["precedenceResource"] == _PRECEDENCE_PATH.name
    names = [
        _require_string(_require_object(case, "cases[]").get("name"), "case.name")
        for case in cases
    ]
    assert names
    assert len(names) == len(set(names))


def test_configuration_override_cases_match_merge_and_snapshot_results() -> None:
    """Verify every Case produces exact sources, values, and safe Snapshot data."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("cases"), "cases")
    sdk_limits = _resolved_resource_limits(
        _require_object(fixture.get("sdkResourceLimits"), "sdkResourceLimits"),
        "sdkResourceLimits",
    )

    # Execute every expected artifact through production merge, validation, and
    # safe mapping rather than reproducing those algorithms inside the test.
    for case_value in cases:
        case = _require_object(case_value, "cases[]")
        layers = _decode_sources(_require_object(case.get("sources"), "case.sources"))
        expected = _require_object(case.get("expected"), "case.expected")
        resolved = _merge_case(layers, sdk_limits)
        assert json_fixtures_equal(
            _resolved_observation(resolved),
            _require_object(expected.get("resolved"), "expected.resolved"),
        )
        assert json_fixtures_equal(
            _selected_sources(resolved, layers, sdk_limits),
            _require_object(
                expected.get("selectedSources"), "expected.selectedSources"
            ),
        )
        assert json_fixtures_equal(
            _snapshot_observation(resolved),
            _require_object(expected.get("safeSnapshot"), "expected.safeSnapshot"),
        )


def test_configuration_override_cases_cover_every_applicable_source_branch() -> None:
    """Verify the table traces all source and per-resource-field branches."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("cases"), "cases")
    coverage: dict[str, set[str | None]] = {
        "target": set(),
        "serviceAccess": set(),
        "compatibilityPolicy": set(),
        "cancellationSignal": set(),
    }
    resource_coverage: dict[str, set[str]] = {
        field_name: set() for field_name in _RESOURCE_FIELDS
    }

    # Coverage is derived from committed expected provenance, then the prior test
    # proves every expected provenance map matches actual production selection.
    for case_value in cases:
        case = _require_object(case_value, "cases[]")
        expected = _require_object(case.get("expected"), "case.expected")
        selected = _require_object(
            expected.get("selectedSources"), "expected.selectedSources"
        )
        for field_name in coverage:
            coverage[field_name].add(
                _optional_string(selected.get(field_name), field_name)
            )
        resources = _require_object(
            selected.get("resourceLimits"), "selectedSources.resourceLimits"
        )
        for field_name in _RESOURCE_FIELDS:
            resource_coverage[field_name].add(
                _require_string(resources.get(field_name), field_name)
            )

    assert coverage == {
        "target": {"request", "client"},
        "serviceAccess": {"interaction", "request", "client", "integration", None},
        "compatibilityPolicy": {"interaction", "client", "sdk_safe_default"},
        "cancellationSignal": {"interaction", None},
    }
    assert all(
        sources == {"interaction", "client", "sdk_safe_default"}
        for sources in resource_coverage.values()
    )
