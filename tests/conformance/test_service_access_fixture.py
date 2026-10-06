"""Conformance checks for language-neutral ServiceAccess fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from mconet.core.domain import (
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    JsonValue,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    UriValue,
    validate_service_access,
)
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
    json_fixtures_equal,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary" / "service-access.json"
)
_INDEX_PATH = _FIXTURE_PATH.parent / "index.json"
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "service-access.json"
_SCHEMA_ID = OpenIdentifier("schema.service_access")
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return immutable empty extensions for omitted Fixture data."""
    # The proxy has no nested values and cannot be mutated, so structural access
    # objects can share it without introducing cross-case mutable state.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class _FixtureAccess:
    """Concrete structural access value reconstructed from one shared case."""

    endpoint: UriValue | None = None
    """Optional absolute endpoint with exact source text preserved."""

    authorization: Authorization | None = None
    """Runtime-only authorization, always absent from ordinary Fixture input."""

    headers: Headers = field(default_factory=Headers)
    """Ordered non-sensitive Header fields reconstructed without normalization."""

    query: QueryParameters = field(default_factory=QueryParameters)
    """Ordered non-sensitive Query fields reconstructed without encoding."""

    api_version: str | None = None
    """Optional provider API version context."""

    project_id: str | None = None
    """Optional provider project context."""

    tenant_id: str | None = None
    """Optional provider tenant context."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown non-sensitive access fields retained as portable JSON."""


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    # A named object envelope prevents language implementations from inventing
    # positional meanings when a malformed Fixture root is encountered.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _require_object(value: JsonValue | None, field_name: str) -> dict[str, JsonValue]:
    """Return one required object-valued field with a stable diagnostic."""
    # Reject missing and non-object data before any field-level decoding so host
    # language casts cannot hide an invalid shared Fixture structure.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_array(value: JsonValue | None, field_name: str) -> list[JsonValue]:
    """Return one required array-valued field with a stable diagnostic."""
    # Arrays retain case and Header/Query order, which are both significant to
    # cross-language conformance and must never be converted to keyed mappings.
    if not isinstance(value, list):
        raise AssertionError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: JsonValue | None, field_name: str) -> str:
    """Return one required string without host-language coercion."""
    # JSON numbers, booleans, null, and containers are deliberately rejected;
    # converting them to text would create platform-dependent access values.
    if not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string.")
    return value


def _optional_string(value: JsonValue | None, field_name: str) -> str | None:
    """Return an optional nullable string and reject every other JSON kind."""
    # Endpoint and provider context fields use the same omission/null contract,
    # while a present non-string indicates an invalid Fixture decoder input.
    if value is not None and not isinstance(value, str):
        raise AssertionError(f"{field_name} must be a JSON string or null.")
    return value


def _decode_headers(document: dict[str, JsonValue]) -> Headers:
    """Decode ordered Header entries without folding case or merging repeats."""
    if "headers" not in document:
        return Headers()
    container = _require_object(document["headers"], "headers")
    values = _require_array(container.get("values"), "headers.values")

    # Construct each nominal value in source order so duplicate names and their
    # original spelling remain available to validation and transport layers.
    fields: list[HeaderField] = []
    for index, value in enumerate(values):
        field = _require_object(value, f"headers.values[{index}]")
        fields.append(
            HeaderField(
                _require_string(field.get("name"), "header.name"),
                _require_string(field.get("value"), "header.value"),
            )
        )
    return Headers(tuple(fields))


def _decode_query(document: dict[str, JsonValue]) -> QueryParameters:
    """Decode ordered Query entries without applying URL encoding."""
    if "query" not in document:
        return QueryParameters()
    container = _require_object(document["query"], "query")
    values = _require_array(container.get("values"), "query.values")

    # Query names remain case-sensitive opaque text and repeated values retain
    # their caller order for the eventual transport-specific encoder.
    parameters: list[QueryParameter] = []
    for index, value in enumerate(values):
        parameter = _require_object(value, f"query.values[{index}]")
        parameters.append(
            QueryParameter(
                _require_string(parameter.get("name"), "query.name"),
                _require_string(parameter.get("value"), "query.value"),
            )
        )
    return QueryParameters(tuple(parameters))


def _decode_extensions(document: dict[str, JsonValue]) -> Extensions:
    """Decode omitted extensions as immutable empty data."""
    # Present extension values remain an uninterpreted JSON object; the public
    # Validator subsequently enforces recursive number portability.
    if "extensions" not in document:
        return _EMPTY_EXTENSIONS
    return _require_object(document["extensions"], "extensions")


def _access_from_document(document: dict[str, JsonValue]) -> _FixtureAccess:
    """Reconstruct one schema-valid document through public domain value types."""
    endpoint_value = _optional_string(document.get("endpoint"), "endpoint")

    # Fixture input never carries Authorization. A non-null endpoint is declared
    # absolute so validate_service_access verifies its syntax and scheme.
    return _FixtureAccess(
        endpoint=(
            UriValue(endpoint_value, True) if endpoint_value is not None else None
        ),
        headers=_decode_headers(document),
        query=_decode_query(document),
        api_version=_optional_string(document.get("apiVersion"), "apiVersion"),
        project_id=_optional_string(document.get("projectId"), "projectId"),
        tenant_id=_optional_string(document.get("tenantId"), "tenantId"),
        extensions=_decode_extensions(document),
    )


def _serialize_access(access: _FixtureAccess) -> dict[str, JsonValue]:
    """Serialize present non-sensitive fields for extension round-trip checks."""
    document: dict[str, JsonValue] = {}

    # Authorization is intentionally never inspected or emitted. Every other
    # optional scalar is copied only when present to avoid inventing null fields.
    if access.endpoint is not None:
        document["endpoint"] = access.endpoint.value
    if access.headers.values:
        document["headers"] = {
            "values": [
                {"name": field.name, "value": field.value}
                for field in access.headers.values
            ]
        }
    if access.query.values:
        document["query"] = {
            "values": [
                {"name": parameter.name, "value": parameter.value}
                for parameter in access.query.values
            ]
        }
    for field_name, value in (
        ("apiVersion", access.api_version),
        ("projectId", access.project_id),
        ("tenantId", access.tenant_id),
    ):
        if value is not None:
            document[field_name] = value
    if access.extensions:
        document["extensions"] = dict(access.extensions)
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the registered ServiceAccess schema through the public adapter."""
    schema = _load_object(_SCHEMA_PATH)
    # The stable schema ID independently selected by the Fixture must match the
    # committed resource before any case result can be considered conformance.
    assert schema.get("$id") == _SCHEMA_ID.value
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _case_document(case: JsonValue, group_name: str) -> dict[str, JsonValue]:
    """Return the named input document from one case object."""
    case_object = _require_object(case, group_name)
    _require_string(case_object.get("name"), f"{group_name}.name")
    return _require_object(case_object.get("input"), f"{group_name}.input")


def _expected_issues(case: dict[str, JsonValue]) -> tuple[SchemaValidationIssue, ...]:
    """Decode exact portable issue objects into adapter result values."""
    issue_values = _require_array(case.get("expectedIssues"), "expectedIssues")
    issues: list[SchemaValidationIssue] = []
    for issue_value in issue_values:
        issue = _require_object(issue_value, "expectedIssues[]")
        # Platform-private diagnostic fields would make the shared result
        # impossible to reproduce, so only the stable triple is admitted.
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


def _named_case(
    cases: list[JsonValue],
    expected_name: str,
) -> dict[str, JsonValue]:
    """Select exactly one case by its language-neutral name."""
    matches = [
        _require_object(case, "cases[]")
        for case in cases
        if isinstance(case, dict) and case.get("name") == expected_name
    ]
    # Exact uniqueness prevents a duplicate from making order assertions depend
    # on whichever matching case a language happens to select first.
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one case named {expected_name!r}.")
    return matches[0]


def test_service_access_fixture_is_registered_with_a_stable_envelope() -> None:
    """Verify discovery metadata and all portable case groups are explicit."""
    index = _load_object(_INDEX_PATH)
    fixture = _load_object(_FIXTURE_PATH)

    # Registration makes the Fixture discoverable across platforms, while an
    # exact envelope forces incompatible format additions through review.
    resources = _require_array(index.get("resources"), "resources")
    assert "service-access.json" in resources
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


def test_service_access_valid_cases_match_schema_and_domain_validation() -> None:
    """Verify every legal non-sensitive case passes both contract layers."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("validCases"), "validCases")
    assert cases

    # Schema validation proves portable payload shape; reconstruction and the
    # public Validator prove the same data satisfies Python domain semantics.
    adapter = _adapter()
    for case in cases:
        document = _case_document(case, "validCases[]")
        assert adapter.validate(_SCHEMA_ID, document) == ()
        access = _access_from_document(document)
        assert access.authorization is None
        assert validate_service_access(access) is access


def test_service_access_repeated_context_preserves_exact_order() -> None:
    """Verify Header spelling and repeated Header/Query order remain unchanged."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("validCases"), "validCases")
    case = _named_case(cases, "ordered-access-context")
    access = _access_from_document(_case_document(case, "validCases[]"))

    # Header lookup is case-insensitive but the stored field sequence keeps its
    # original spelling; Query values remain exact caller-ordered pairs.
    assert access.headers.values == (
        HeaderField("X-Feature", "first"),
        HeaderField("x-feature", "second"),
    )
    assert access.headers.get_all("X-FEATURE") == ("first", "second")
    assert access.query.values == (
        QueryParameter("tag", "first"),
        QueryParameter("tag", "second"),
    )


def test_service_access_invalid_cases_produce_exact_schema_issues() -> None:
    """Verify every illegal case produces shared deterministic diagnostics."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(fixture.get("invalidCases"), "invalidCases")
    assert cases

    # Complete tuples freeze path, keyword, message, and issue ordering instead
    # of allowing platform-specific tests to assert only generic failure.
    adapter = _adapter()
    for case_value in cases:
        case = _require_object(case_value, "invalidCases[]")
        document = _case_document(case, "invalidCases[]")
        assert adapter.validate(_SCHEMA_ID, document) == _expected_issues(case)


def test_service_access_unknown_extensions_round_trip_without_authorization() -> None:
    """Verify unknown non-sensitive data survives without serializing authorization."""
    fixture = _load_object(_FIXTURE_PATH)
    cases = _require_array(
        fixture.get("unknownExtensionCases"), "unknownExtensionCases"
    )
    assert cases

    # Validation precedes serialization so canonical equality cannot hide an
    # invalid extension; the output path has no Authorization mapping at all.
    adapter = _adapter()
    for case_value in cases:
        case = _require_object(case_value, "unknownExtensionCases[]")
        document = _case_document(case, "unknownExtensionCases[]")
        expected = _require_object(
            case.get("expected"), "unknownExtensionCases[].expected"
        )
        assert adapter.validate(_SCHEMA_ID, document) == ()
        access = _access_from_document(document)
        validate_service_access(access)
        serialized = _serialize_access(access)
        assert "authorization" not in serialized
        assert json_fixtures_equal(serialized, expected)
