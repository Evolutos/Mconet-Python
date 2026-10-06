"""Conformance checks for language-neutral ModelTarget fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from mconet.core.domain import (
    Extensions,
    JsonValue,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    validate_model_target,
)
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
    json_fixtures_equal,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary" / "model-target.json"
)
_INDEX_PATH = _FIXTURE_PATH.parent / "index.json"
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "model-target.json"
_SCHEMA_ID = OpenIdentifier("schema.model_target")
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return an immutable empty mapping for omitted fixture extension fields."""
    # The shared proxy has no nested data and cannot be mutated, so it is safe
    # for multiple test values while keeping omission distinct from fixture data.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _FixtureTarget:
    """Concrete structural target reconstructed from a language-neutral case."""

    service_id: OpenIdentifier
    """Service identifier decoded without inferring provider behavior."""

    protocol_id: OpenIdentifier
    """Protocol identifier kept independent from the selected service."""

    model: ModelDescriptor
    """Model descriptor reconstructed from the nested fixture object."""

    deployment_id: str | None = None
    """Optional opaque deployment identifier."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown target fields retained as portable JSON values."""


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    # Requiring a named object envelope prevents a malformed array fixture from
    # being interpreted differently by language-specific conformance runners.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued field with a stable diagnostic."""
    # Missing values and non-object values fail at the fixture boundary before
    # tests perform field-level casts or construct domain implementations.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued field with a stable diagnostic."""
    # Case groups are arrays because source order is part of the shared fixture
    # and duplicate case documents remain detectable rather than overwritten.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string-valued field without implicit coercion."""
    # Cross-language fixtures cannot rely on host-language string conversion;
    # an absent, null, numeric, or composite field is therefore rejected here.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string while rejecting every other JSON kind."""
    # Optional descriptor and deployment fields share the same explicit-null
    # representation, so one helper enforces their portable decoding rule.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _optional_extensions(
    document: dict[str, JsonValue],
    field_name: str,
) -> Extensions:
    """Decode an omitted extension mapping as immutable empty data."""
    # A present mapping is preserved directly for equality checks; an omitted
    # field receives a read-only empty value without inventing extension keys.
    if field_name not in document:
        return _EMPTY_EXTENSIONS
    return _require_object(document[field_name], field_name)


def _target_from_document(document: dict[str, JsonValue]) -> _FixtureTarget:
    """Reconstruct one schema-valid document through public domain value types."""
    model_document = _require_object(document.get("model"), "model")
    family_value = _optional_string(model_document.get("family"), "model.family")

    # Every identifier is wrapped explicitly so the public validator applies the
    # same open-identifier semantics used by production structural targets.
    model = NamedModel(
        name=_require_string(model_document.get("name"), "model.name"),
        display_name=_optional_string(
            model_document.get("displayName"), "model.displayName"
        ),
        family=OpenIdentifier(family_value) if family_value is not None else None,
        version=_optional_string(model_document.get("version"), "model.version"),
        description=_optional_string(
            model_document.get("description"), "model.description"
        ),
        metadata=_optional_extensions(model_document, "metadata"),
        extensions=_optional_extensions(model_document, "extensions"),
    )
    return _FixtureTarget(
        service_id=OpenIdentifier(
            _require_string(document.get("serviceId"), "serviceId")
        ),
        protocol_id=OpenIdentifier(
            _require_string(document.get("protocolId"), "protocolId")
        ),
        model=model,
        deployment_id=_optional_string(document.get("deploymentId"), "deploymentId"),
        extensions=_optional_extensions(document, "extensions"),
    )


def _serialize_target(target: _FixtureTarget) -> dict[str, JsonValue]:
    """Serialize a reconstructed target for unknown-extension round-trip checks."""
    model = target.model
    model_document: dict[str, JsonValue] = {"name": model.name}

    # Optional scalar values are emitted when present; extension and metadata
    # mappings are copied without interpreting provider-owned keys or values.
    for field_name, value in (
        ("displayName", model.display_name),
        ("version", model.version),
        ("description", model.description),
    ):
        if value is not None:
            model_document[field_name] = value
    if model.family is not None:
        model_document["family"] = model.family.value
    if model.metadata:
        model_document["metadata"] = dict(model.metadata)
    if model.extensions:
        model_document["extensions"] = dict(model.extensions)

    document: dict[str, JsonValue] = {
        "serviceId": target.service_id.value,
        "protocolId": target.protocol_id.value,
        "model": model_document,
    }
    if target.deployment_id is not None:
        document["deploymentId"] = target.deployment_id
    if target.extensions:
        document["extensions"] = dict(target.extensions)
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the registered ModelTarget schema through the public test adapter."""
    schema = _load_object(_SCHEMA_PATH)
    # Fixture lookup and schema registration use the same stable identifier;
    # checking it here prevents a silently valid but disconnected resource.
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _case_document(case: JsonValue, group_name: str) -> dict[str, JsonValue]:
    """Return the input document from one named case object."""
    case_object = _require_object(case, group_name)
    _require_string(case_object.get("name"), f"{group_name}.name")
    return _require_object(case_object.get("input"), f"{group_name}.input")


def _expected_issues(case: dict[str, JsonValue]) -> tuple[SchemaValidationIssue, ...]:
    """Decode exact portable issue objects into adapter result values."""
    issue_values = _require_array(case.get("expectedIssues"), "expectedIssues")
    issues: list[SchemaValidationIssue] = []
    for issue_value in issue_values:
        issue = _require_object(issue_value, "expectedIssues[]")
        # Exact key equality prevents platform-only diagnostic data from entering
        # a fixture intended to produce identical cross-language results.
        if frozenset(issue) != frozenset({"path", "keyword", "message"}):
            raise AssertionError("Each expected issue must have exactly three fields.")
        issues.append(
            SchemaValidationIssue(
                path=_require_string(issue.get("path"), "issue.path"),
                keyword=_require_string(issue.get("keyword"), "issue.keyword"),
                message=_require_string(issue.get("message"), "issue.message"),
            )
        )
    return tuple(issues)


def test_model_target_fixture_is_registered_with_a_stable_envelope() -> None:
    """Verify discovery metadata and all portable case groups are explicit."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)

    # An orphan fixture cannot participate in other language implementations;
    # exact envelope fields also make incompatible format changes visible.
    resources = _require_array(index.get("resources"), "resources")
    assert "model-target.json" in resources
    assert frozenset(fixture) == frozenset(
        {
            "format_version",
            "schemaId",
            "validCases",
            "invalidCases",
            "unknownExtensionCases",
        }
    )
    assert fixture["format_version"] == 1
    assert fixture["schemaId"] == _SCHEMA_ID.value


def test_model_target_valid_cases_match_schema_and_domain_validation() -> None:
    """Verify every legal case passes both portable and runtime contracts."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("validCases"), "validCases")
    assert cases

    # Schema acceptance proves portable shape while domain validation proves the
    # Python implementation reconstructs the same separated target dimensions.
    adapter = _adapter()
    for case in cases:
        document = _case_document(case, "validCases[]")
        assert adapter.validate(_SCHEMA_ID, document) == ()
        target = _target_from_document(document)
        assert validate_model_target(target) is target


def test_model_target_invalid_cases_produce_exact_schema_issues() -> None:
    """Verify every illegal case produces the shared deterministic diagnostics."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("invalidCases"), "invalidCases")
    assert cases

    # Each complete issue tuple is compared rather than merely requiring failure,
    # freezing paths, keywords, messages, and ordering for every implementation.
    adapter = _adapter()
    for case_value in cases:
        case = _require_object(case_value, "invalidCases[]")
        document = _case_document(case, "invalidCases[]")
        assert adapter.validate(_SCHEMA_ID, document) == _expected_issues(case)


def test_model_target_unknown_extensions_round_trip_without_interpretation() -> None:
    """Verify nested model and target extensions survive a domain round trip."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(
        fixture.get("unknownExtensionCases"), "unknownExtensionCases"
    )
    assert cases

    # Schema and semantic validation run before serialization so equality cannot
    # conceal invalid extensions that happened to be copied byte-for-byte.
    adapter = _adapter()
    for case_value in cases:
        case = _require_object(case_value, "unknownExtensionCases[]")
        document = _case_document(case, "unknownExtensionCases[]")
        expected = _require_object(
            case.get("expected"), "unknownExtensionCases[].expected"
        )
        assert adapter.validate(_SCHEMA_ID, document) == ()
        target = _target_from_document(document)
        validate_model_target(target)
        assert json_fixtures_equal(_serialize_target(target), expected)
